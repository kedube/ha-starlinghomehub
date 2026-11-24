"""Tests for camera entities and camera-derived sensors."""

import asyncio
from urllib.parse import unquote, urlsplit

from custom_components.starling_home_hub.integrations.camera import get_camera_dynamic_binary_sensor_entities
from custom_components.starling_home_hub.integrations.camera_rtsp import StarlingHomeHubRTSPCamera
from custom_components.starling_home_hub.integrations.camera_webrtc import StarlingHomeHubWebRTCCamera
from custom_components.starling_home_hub.models.api.stream import StartStream
from tests.helpers import CAM, make_coordinator


def _stream_for(device_id, sdp_offer):
    return StartStream(status="OK", answer=f"answer-{sdp_offer}", streamId=f"s-{sdp_offer}", isLocal=True)


def test_each_zone_sensor_reads_its_own_zone():
    """Dynamic zone and face sensors each read their own key."""
    device = {"zoneActivityDetected:Driveway": True,
              "zoneActivityDetected:Porch": False,
              "faceDetected:Alice": False}
    values = {d.key: d.value_fn(device) for d in get_camera_dynamic_binary_sensor_entities(device)}
    assert values == {"zone_activity_detected_driveway": True,
                      "zone_activity_detected_porch": False,
                      "face_detected_alice": False}


async def test_second_viewer_gets_answer_for_its_own_offer(hass):
    """Each WebRTC session gets its own stream; closing one leaves the other running."""
    coord = make_coordinator({"cam1": CAM})
    coord.start_stream.side_effect = _stream_for
    cam = StarlingHomeHubWebRTCCamera("cam1", coord)
    cam.hass = hass
    sent = {}
    try:
        await cam.async_handle_async_webrtc_offer("A", "sess-A", lambda m: sent.__setitem__("A", m.answer))
        await cam.async_handle_async_webrtc_offer("B", "sess-B", lambda m: sent.__setitem__("B", m.answer))
        cam.close_webrtc_session("sess-A")
        await hass.async_block_till_done()
        assert sent == {"A": "answer-A", "B": "answer-B"}
        coord.stop_stream.assert_awaited_once_with("cam1", "s-A")
    finally:
        await cam.async_will_remove_from_hass()


async def test_concurrent_offers_do_not_leak_hub_streams(hass):
    """Two offers racing each other both get stopped when their sessions close."""
    gate = asyncio.Event()

    async def slow_start(device_id, sdp_offer):
        await gate.wait()
        return _stream_for(device_id, sdp_offer)

    coord = make_coordinator({"cam1": CAM})
    coord.start_stream.side_effect = slow_start
    cam = StarlingHomeHubWebRTCCamera("cam1", coord)
    cam.hass = hass
    try:
        t1 = hass.async_create_task(cam.async_handle_async_webrtc_offer("A", "sess-A", lambda m: None))
        t2 = hass.async_create_task(cam.async_handle_async_webrtc_offer("B", "sess-B", lambda m: None))
        await asyncio.sleep(0)
        gate.set()
        await asyncio.gather(t1, t2)
        cam.close_webrtc_session("sess-A")
        cam.close_webrtc_session("sess-B")
        await hass.async_block_till_done()
        assert {c.args[1] for c in coord.stop_stream.await_args_list} == {"s-A", "s-B"}
    finally:
        await cam.async_will_remove_from_hass()


async def test_session_closed_during_start_still_stops_its_stream(hass):
    """A viewer that leaves before the hub answers doesn't leave an orphaned stream."""
    gate = asyncio.Event()

    async def slow_start(device_id, sdp_offer):
        await gate.wait()
        return _stream_for(device_id, sdp_offer)

    coord = make_coordinator({"cam1": CAM})
    coord.start_stream.side_effect = slow_start
    cam = StarlingHomeHubWebRTCCamera("cam1", coord)
    cam.hass = hass
    sent = []
    try:
        task = hass.async_create_task(cam.async_handle_async_webrtc_offer("A", "sess-A", sent.append))
        await asyncio.sleep(0)
        cam.close_webrtc_session("sess-A")
        gate.set()
        await task
        coord.stop_stream.assert_awaited_once_with("cam1", "s-A")
        assert sent == []
    finally:
        await cam.async_will_remove_from_hass()


async def test_rtsp_credentials_are_url_encoded():
    """Special characters in RTSP credentials can't change the stream's host."""
    cam = StarlingHomeHubRTSPCamera("cam1", make_coordinator({"cam1": CAM}),
                                    rtsp_username="admin", rtsp_password="p@ss/w:rd#1")
    parts = urlsplit(await cam.stream_source())
    assert (parts.hostname, parts.port) == ("192.168.1.10", 8554)
    assert unquote(parts.password) == "p@ss/w:rd#1"
