using Unity.Mathematics;
using UnityEngine;
using UnityEngine.Splines;

namespace ChaosOne.Scenarios
{
    /// <summary>
    /// Procedurally builds a depressed-trajectory spline on a SplineContainer
    /// at scene boot, removing the need to hand-author the M1 hero-shot spline
    /// in the Splines editor. Three knot positions define the arc:
    ///   - Boost: high climb-out near the launch point.
    ///   - Apogee: a relatively low peak (this is what makes the trajectory
    ///     "depressed" versus a classical ballistic profile).
    ///   - Terminal: descent toward the aimpoint.
    /// Tangents are oriented along the path direction so SplineUtility's
    /// tangent evaluation gives the threat its heading.
    /// </summary>
    [RequireComponent(typeof(SplineContainer))]
    public sealed class DepressedTrajectoryBuilder : MonoBehaviour
    {
        [Header("Geometry (world meters)")]
        [SerializeField] private Vector3 launchPoint = new(-12_000f, 100f, 0f);
        [SerializeField] private Vector3 apogeePoint = new(0f, 32_000f, 0f);
        [SerializeField] private Vector3 terminalPoint = new(12_000f, 800f, 0f);

        [Header("Shape")]
        [SerializeField] private float boostTangentScale = 4000f;
        [SerializeField] private float apogeeTangentScale = 9000f;
        [SerializeField] private float terminalTangentScale = 5000f;

        [Header("Behavior")]
        [SerializeField] private bool buildOnAwake = true;
        [SerializeField] private bool rebuildOnValidate = true;

        private SplineContainer container;

        private void Awake()
        {
            container = GetComponent<SplineContainer>();
            if (buildOnAwake) Build();
        }

        private void OnValidate()
        {
            if (!rebuildOnValidate) return;
            if (container == null) container = GetComponent<SplineContainer>();
            if (container != null) Build();
        }

        public void Build()
        {
            if (container == null) return;

            var spline = container.Spline ?? new Spline();
            spline.Clear();

            var launchTangent = (apogeePoint - launchPoint).normalized * boostTangentScale;
            var apogeeTangent = (terminalPoint - launchPoint).normalized * apogeeTangentScale;
            var terminalTangent = (terminalPoint - apogeePoint).normalized * terminalTangentScale;

            spline.Add(new BezierKnot(
                position: (float3)launchPoint,
                tangentIn: -(float3)launchTangent,
                tangentOut: (float3)launchTangent));

            spline.Add(new BezierKnot(
                position: (float3)apogeePoint,
                tangentIn: -(float3)apogeeTangent,
                tangentOut: (float3)apogeeTangent));

            spline.Add(new BezierKnot(
                position: (float3)terminalPoint,
                tangentIn: -(float3)terminalTangent,
                tangentOut: (float3)terminalTangent));

            spline.Closed = false;
            container.Spline = spline;
        }
    }
}
