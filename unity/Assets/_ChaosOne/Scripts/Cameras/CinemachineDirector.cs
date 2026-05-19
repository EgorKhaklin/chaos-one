using Unity.Cinemachine;
using UnityEngine;

namespace ChaosOne.Cameras
{
    public enum CameraPreset
    {
        SideAltitude,
        TopDown,
        TerminalZoom,
        FollowTrack,
    }

    /// <summary>
    /// Switches between named Cinemachine cameras by raising the chosen
    /// camera's priority above the rest. Cinemachine handles the blend.
    /// </summary>
    public sealed class CinemachineDirector : MonoBehaviour
    {
        [SerializeField] private CinemachineCamera sideAltitudeCam;
        [SerializeField] private CinemachineCamera topDownCam;
        [SerializeField] private CinemachineCamera terminalZoomCam;
        [SerializeField] private CinemachineCamera followTrackCam;
        [SerializeField] private CameraPreset initialPreset = CameraPreset.SideAltitude;

        private const int ActivePriority = 100;
        private const int InactivePriority = 0;

        private CinemachineCamera active;

        public CameraPreset CurrentPreset { get; private set; }

        private void Start()
        {
            SnapTo(initialPreset);
        }

        public void SnapTo(CameraPreset preset)
        {
            var target = Resolve(preset);
            if (target == null) return;

            if (active != null && active != target)
            {
                active.Priority = InactivePriority;
            }

            target.Priority = ActivePriority;
            active = target;
            CurrentPreset = preset;
        }

        public void SetFollowTarget(Transform target)
        {
            if (followTrackCam == null) return;
            followTrackCam.Follow = target;
            followTrackCam.LookAt = target;
        }

        private CinemachineCamera Resolve(CameraPreset preset) => preset switch
        {
            CameraPreset.SideAltitude => sideAltitudeCam,
            CameraPreset.TopDown => topDownCam,
            CameraPreset.TerminalZoom => terminalZoomCam,
            CameraPreset.FollowTrack => followTrackCam,
            _ => sideAltitudeCam,
        };
    }
}
