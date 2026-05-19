using UnityEngine;
using UnityEngine.InputSystem;

namespace ChaosOne.Cameras
{
    /// <summary>
    /// Maps the digit keys to camera presets on a CinemachineDirector.
    /// 1 = side altitude, 2 = top down, 3 = terminal zoom, 4 = follow track.
    /// </summary>
    [RequireComponent(typeof(CinemachineDirector))]
    public sealed class CameraInputController : MonoBehaviour
    {
        private CinemachineDirector director;

        private void Awake()
        {
            director = GetComponent<CinemachineDirector>();
        }

        private void Update()
        {
            var keyboard = Keyboard.current;
            if (keyboard == null) return;

            if (keyboard.digit1Key.wasPressedThisFrame) director.SnapTo(CameraPreset.SideAltitude);
            else if (keyboard.digit2Key.wasPressedThisFrame) director.SnapTo(CameraPreset.TopDown);
            else if (keyboard.digit3Key.wasPressedThisFrame) director.SnapTo(CameraPreset.TerminalZoom);
            else if (keyboard.digit4Key.wasPressedThisFrame) director.SnapTo(CameraPreset.FollowTrack);
        }
    }
}
