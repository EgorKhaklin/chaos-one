using ChaosOne.Threats;
using UnityEngine;

namespace ChaosOne.Scenarios
{
    /// <summary>
    /// Sweeps a single ThreatTrack along a depressed-trajectory parabola
    /// so the camera sees motion and the TrackInfoPanel has live
    /// kinematic data to render when the track is clicked.
    ///
    /// Replaced when the full Stage rendering pipeline lands (envelope
    /// shaders + spline-driven WraithDirector against a real
    /// ThreatArchetype).
    /// </summary>
    [RequireComponent(typeof(ThreatTrack))]
    public sealed class DemoTrackMover : MonoBehaviour
    {
        [SerializeField] private Vector3 launchPoint = new(-9000f, 200f, 0f);
        [SerializeField] private Vector3 apogeePoint = new(0f, 18000f, 0f);
        [SerializeField] private Vector3 terminalPoint = new(9000f, 400f, 0f);
        [SerializeField] private float traverseSeconds = 12f;
        [SerializeField] private float restartPauseSeconds = 1.5f;
        [SerializeField] private float minSpeedMps = 1800f;
        [SerializeField] private float maxSpeedMps = 6200f;

        private ThreatTrack track;
        private float elapsed;
        private bool restarting;
        private float restartTimer;
        private Vector3 lastPosition;

        private void Awake()
        {
            track = GetComponent<ThreatTrack>();
        }

        private void Start()
        {
            transform.position = launchPoint;
            lastPosition = launchPoint;
            track.SetState(TrackState.ConfidentRV);
        }

        private void Update()
        {
            if (restarting)
            {
                restartTimer += Time.deltaTime;
                if (restartTimer >= restartPauseSeconds)
                {
                    restarting = false;
                    restartTimer = 0f;
                    elapsed = 0f;
                }
                return;
            }

            elapsed += Time.deltaTime;
            var t = Mathf.Clamp01(elapsed / traverseSeconds);

            // Quadratic Bezier through the three control points.
            var p01 = Vector3.Lerp(launchPoint, apogeePoint, t);
            var p12 = Vector3.Lerp(apogeePoint, terminalPoint, t);
            var position = Vector3.Lerp(p01, p12, t);

            var dt = Mathf.Max(Time.deltaTime, 1e-4f);
            var velocity = (position - lastPosition) / dt;
            var speed = velocity.magnitude;
            if (speed < 0.01f)
            {
                speed = Mathf.Lerp(maxSpeedMps, minSpeedMps, t);
            }

            var orientation = velocity.sqrMagnitude > 1e-6f
                ? Quaternion.LookRotation(velocity, Vector3.up)
                : transform.rotation;

            var sample = new KinematicSample(
                position: position,
                orientation: orientation,
                velocity: velocity,
                speedMps: speed,
                altitudeMeters: Mathf.Max(0f, position.y),
                confidence: Mathf.Lerp(0.65f, 0.95f, Mathf.SmoothStep(0f, 1f, t)),
                capturedAt: Time.timeAsDouble);

            track.ApplySample(sample);
            lastPosition = position;

            if (t >= 1f)
            {
                restarting = true;
            }
        }
    }
}
