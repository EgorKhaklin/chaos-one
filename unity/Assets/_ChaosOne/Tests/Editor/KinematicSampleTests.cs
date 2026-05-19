using ChaosOne.Threats;
using NUnit.Framework;
using UnityEngine;

namespace ChaosOne.Tests
{
    public sealed class KinematicSampleTests
    {
        [Test]
        public void MachNumber_Is_Speed_Over_343()
        {
            var sample = new KinematicSample(
                position: Vector3.zero,
                orientation: Quaternion.identity,
                velocity: Vector3.forward * 686f,
                speedMps: 686f,
                altitudeMeters: 30_000f,
                confidence: 0.9f,
                capturedAt: 0.0);

            Assert.That(sample.MachNumber, Is.EqualTo(2f).Within(1e-3));
        }

        [Test]
        public void Confidence_Is_Clamped_To_Unit_Interval()
        {
            var below = new KinematicSample(
                Vector3.zero, Quaternion.identity, Vector3.zero,
                speedMps: 0f, altitudeMeters: 0f, confidence: -0.5f, capturedAt: 0.0);
            var above = new KinematicSample(
                Vector3.zero, Quaternion.identity, Vector3.zero,
                speedMps: 0f, altitudeMeters: 0f, confidence: 1.5f, capturedAt: 0.0);

            Assert.That(below.Confidence, Is.EqualTo(0f));
            Assert.That(above.Confidence, Is.EqualTo(1f));
        }
    }
}
