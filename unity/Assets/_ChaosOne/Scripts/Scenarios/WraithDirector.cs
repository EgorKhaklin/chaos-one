using ChaosOne.Threats;
using Unity.Mathematics;
using UnityEngine;
using UnityEngine.Splines;

namespace ChaosOne.Scenarios
{
    /// <summary>
    /// Drives the M1 hero shot: an HGV traverses a depressed-trajectory spline
    /// while a moving aimpoint translates beneath it. Hand-authored spline
    /// preferred; physics integration arrives in M3 alongside the backend.
    /// </summary>
    public sealed class WraithDirector : MonoBehaviour
    {
        [Header("Threat")]
        [SerializeField] private GameObject threatPrefab;
        [SerializeField] private ThreatArchetype archetype;
        [SerializeField] private SplineContainer trajectorySpline;
        [SerializeField] private float traverseDurationSeconds = 60f;
        [SerializeField] private string trackId = "HGV-WRAITH-01";

        [Header("Aimpoint")]
        [SerializeField] private Transform aimpoint;
        [SerializeField] private Vector3 aimpointDirection = Vector3.right;
        [SerializeField] private float aimpointSpeedMps = 12f;

        [Header("Loop")]
        [SerializeField] private bool loop = true;
        [SerializeField] private float pauseBetweenLoopsSeconds = 2f;

        private ThreatTrack track;
        private float elapsed;
        private float pauseRemaining;
        private Vector3 lastPosition;
        private bool loopComplete;

        private void Awake()
        {
            if (trajectorySpline == null)
            {
                Debug.LogError($"{nameof(WraithDirector)}: trajectorySpline not assigned.");
                enabled = false;
                return;
            }

            track = SpawnTrack();
            ApplySampleAt(0f);
        }

        private void Update()
        {
            if (track == null) return;

            if (pauseRemaining > 0f)
            {
                pauseRemaining -= Time.deltaTime;
                return;
            }

            elapsed += Time.deltaTime;
            var t = Mathf.Clamp01(elapsed / traverseDurationSeconds);
            ApplySampleAt(t);

            if (aimpoint != null)
            {
                aimpoint.position += aimpointDirection.normalized * (aimpointSpeedMps * Time.deltaTime);
            }

            if (t >= 1f && !loopComplete)
            {
                loopComplete = true;
                if (loop)
                {
                    pauseRemaining = pauseBetweenLoopsSeconds;
                    elapsed = 0f;
                    loopComplete = false;
                }
            }
        }

        private ThreatTrack SpawnTrack()
        {
            GameObject instance;
            if (threatPrefab != null)
            {
                instance = Instantiate(threatPrefab, transform);
            }
            else
            {
                instance = new GameObject($"Threat_{trackId}");
                instance.transform.SetParent(transform, worldPositionStays: false);

                if (archetype != null && archetype.HullMesh != null)
                {
                    var filter = instance.AddComponent<MeshFilter>();
                    filter.sharedMesh = archetype.HullMesh;
                    var renderer = instance.AddComponent<MeshRenderer>();
                    renderer.sharedMaterial = archetype.HullMaterial;
                }
            }

            var component = instance.GetComponent<ThreatTrack>();
            if (component == null) component = instance.AddComponent<ThreatTrack>();

            component.Configure(archetype, trackId, TrackState.ConfidentRV);

            EnsureCollider(instance);

            return component;
        }

        private void ApplySampleAt(float t)
        {
            var localPosition = SplineUtility.EvaluatePosition(trajectorySpline.Spline, t);
            var localTangent = SplineUtility.EvaluateTangent(trajectorySpline.Spline, t);

            var worldPosition = trajectorySpline.transform.TransformPoint((Vector3)localPosition);
            var worldTangent = trajectorySpline.transform.TransformDirection(((Vector3)localTangent).normalized);

            var orientation = worldTangent.sqrMagnitude > 1e-6f
                ? Quaternion.LookRotation(worldTangent, Vector3.up)
                : Quaternion.identity;

            var velocity = (worldPosition - lastPosition) / Mathf.Max(Time.deltaTime, 1e-4f);
            lastPosition = worldPosition;

            var speed = velocity.magnitude;
            if (speed < 0.01f && archetype != null)
            {
                speed = Mathf.Lerp(archetype.MaxSpeedMps, archetype.MinSpeedMps, t);
            }

            var altitude = Mathf.Max(0f, worldPosition.y);
            var confidence = Mathf.Lerp(0.62f, 0.96f, Mathf.SmoothStep(0f, 1f, t));

            var sample = new KinematicSample(
                position: worldPosition,
                orientation: orientation,
                velocity: velocity,
                speedMps: speed,
                altitudeMeters: altitude,
                confidence: confidence,
                capturedAt: Time.timeAsDouble);

            track.ApplySample(sample);
        }

        private static void EnsureCollider(GameObject target)
        {
            if (target.GetComponent<Collider>() != null) return;
            var collider = target.AddComponent<SphereCollider>();
            collider.isTrigger = true;
            collider.radius = 1.5f;
        }
    }
}
