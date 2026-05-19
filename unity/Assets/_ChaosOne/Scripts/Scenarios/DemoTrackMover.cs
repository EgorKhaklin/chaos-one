using UnityEngine;

namespace ChaosOne.Scenarios
{
    /// <summary>
    /// Lightweight stand-in for a real ThreatTrack in the auto-built
    /// Battlespace scene. Sweeps a single transform along a depressed-
    /// trajectory parabola so the camera sees motion without requiring
    /// any of the production track / archetype / trail pipeline.
    ///
    /// Replaced when the full Stage rendering pipeline lands (ThreatTrack
    /// + TrackVisuals + envelope shaders on a real Cinemachine target).
    /// </summary>
    public sealed class DemoTrackMover : MonoBehaviour
    {
        [SerializeField] private Vector3 launchPoint = new(-9000f, 200f, 0f);
        [SerializeField] private Vector3 apogeePoint = new(0f, 18000f, 0f);
        [SerializeField] private Vector3 terminalPoint = new(9000f, 400f, 0f);
        [SerializeField] private float traverseSeconds = 12f;
        [SerializeField] private float restartPauseSeconds = 1.5f;
        [SerializeField] private bool faceVelocity = true;

        private float elapsed;
        private bool restarting;
        private float restartTimer;
        private Vector3 lastPosition;

        private void Start()
        {
            transform.position = launchPoint;
            lastPosition = launchPoint;
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

            // Quadratic Bezier through the three control points; gives a
            // visually recognizable depressed-trajectory arc without
            // needing a Splines asset.
            var p01 = Vector3.Lerp(launchPoint, apogeePoint, t);
            var p12 = Vector3.Lerp(apogeePoint, terminalPoint, t);
            var position = Vector3.Lerp(p01, p12, t);

            transform.position = position;
            if (faceVelocity)
            {
                var delta = position - lastPosition;
                if (delta.sqrMagnitude > 1e-6f)
                {
                    transform.rotation = Quaternion.LookRotation(delta, Vector3.up);
                }
            }
            lastPosition = position;

            if (t >= 1f)
            {
                restarting = true;
            }
        }
    }
}
