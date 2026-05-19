using ChaosOne.Decisions;
using NUnit.Framework;
using UnityEngine;

namespace ChaosOne.Tests
{
    public sealed class ROEEnvelopeTests
    {
        private ROEEnvelope envelope;

        [SetUp]
        public void SetUp()
        {
            envelope = ScriptableObject.CreateInstance<ROEEnvelope>();
        }

        [TearDown]
        public void TearDown()
        {
            if (envelope != null) Object.DestroyImmediate(envelope);
        }

        private static CourseOfAction Coa(EscalationLevel escalation) =>
            new(
                id: "COA-X",
                headline: "x",
                whyOneLine: "y",
                expectedLeakage: new OutcomeBand(0.05f, 0.02f, 0.08f),
                cost: new MagazineDelta(ngi: 1),
                escalation: escalation,
                releasability: "NATO",
                countdownSeconds: 5f,
                isRecommended: true);

        [Test]
        public void Default_Envelope_Permits_Auto_Authorize_Within_Escalation_Ceiling()
        {
            Assert.That(envelope.AutoAuthorizeOnCountdownExpiry, Is.True);
            Assert.That(envelope.PermitsAutoAuthorize(Coa(EscalationLevel.Low)), Is.True);
            Assert.That(envelope.PermitsAutoAuthorize(Coa(EscalationLevel.Moderate)), Is.True);
        }

        [Test]
        public void Default_Envelope_Refuses_Auto_Authorize_Above_Escalation_Ceiling()
        {
            Assert.That(envelope.PermitsAutoAuthorize(Coa(EscalationLevel.Elevated)), Is.False);
            Assert.That(envelope.PermitsAutoAuthorize(Coa(EscalationLevel.High)), Is.False);
            Assert.That(envelope.PermitsAutoAuthorize(Coa(EscalationLevel.Strategic)), Is.False);
        }
    }
}
