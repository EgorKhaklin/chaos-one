using UnityEngine;

namespace ChaosOne.Cameras
{
    /// <summary>
    /// Slowly orbits a transform around a fixed pivot at a constant
    /// radius and height, always looking at a focus point above the
    /// pivot. Attached to the side-altitude Cinemachine virtual camera
    /// so the perspective drifts during play without requiring full
    /// Follow rigging.
    /// </summary>
    public sealed class OrbitalCamera : MonoBehaviour
    {
        [SerializeField] private Vector3 pivot = new(0f, 0f, 0f);
        [SerializeField] private float radius = 12_000f;
        [SerializeField] private float height = 3_000f;
        [SerializeField] private float angularSpeedDegPerSec = 4f;
        [SerializeField] private float startAngleDeg = 200f;
        [SerializeField] private Vector3 lookOffset = new(0f, 4_000f, 0f);

        private float angleDeg;

        private void Start()
        {
            angleDeg = startAngleDeg;
            UpdatePose();
        }

        private void Update()
        {
            angleDeg = (angleDeg + angularSpeedDegPerSec * Time.deltaTime) % 360f;
            UpdatePose();
        }

        private void UpdatePose()
        {
            var rad = angleDeg * Mathf.Deg2Rad;
            var offset = new Vector3(Mathf.Sin(rad) * radius, height, Mathf.Cos(rad) * radius);
            transform.position = pivot + offset;
            transform.LookAt(pivot + lookOffset);
        }
    }
}
