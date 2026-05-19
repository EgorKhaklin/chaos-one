using UnityEngine;

namespace ChaosOne.Threats
{
    /// <summary>
    /// A point-in-time observation of a track's kinematic state plus
    /// the fusion-layer confidence attached to it. Immutable.
    /// </summary>
    public readonly struct KinematicSample
    {
        public readonly Vector3 Position;
        public readonly Quaternion Orientation;
        public readonly Vector3 Velocity;
        public readonly float SpeedMps;
        public readonly float AltitudeMeters;
        public readonly float Confidence;
        public readonly double CapturedAt;

        public KinematicSample(
            Vector3 position,
            Quaternion orientation,
            Vector3 velocity,
            float speedMps,
            float altitudeMeters,
            float confidence,
            double capturedAt)
        {
            Position = position;
            Orientation = orientation;
            Velocity = velocity;
            SpeedMps = speedMps;
            AltitudeMeters = altitudeMeters;
            Confidence = Mathf.Clamp01(confidence);
            CapturedAt = capturedAt;
        }

        public float MachNumber => SpeedMps / 343f;
    }
}
