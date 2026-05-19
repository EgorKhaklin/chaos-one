using ChaosOne.Decisions;
using NUnit.Framework;

namespace ChaosOne.Tests
{
    public sealed class DecisionDataTests
    {
        [Test]
        public void OutcomeBand_Width_Is_High_Minus_Low()
        {
            var band = new OutcomeBand(point: 0.05f, low: 0.02f, high: 0.08f);
            Assert.That(band.BandWidth, Is.EqualTo(0.06f).Within(1e-6));
        }

        [Test]
        public void MagazineDelta_NonKineticOnly_True_When_HEL_Only()
        {
            var delta = new MagazineDelta(helMegajoules: 0.4f);
            Assert.That(delta.IsNonKineticOnly, Is.True);
        }

        [Test]
        public void MagazineDelta_NonKineticOnly_False_When_NGI_Present()
        {
            var delta = new MagazineDelta(ngi: 1, helMegajoules: 0.4f);
            Assert.That(delta.IsNonKineticOnly, Is.False);
        }

        [Test]
        public void CourseOfAction_Preserves_Fields()
        {
            var coa = new CourseOfAction(
                id: "COA-X",
                headline: "headline",
                whyOneLine: "why",
                expectedLeakage: new OutcomeBand(0.1f, 0.05f, 0.15f),
                cost: new MagazineDelta(ngi: 2),
                escalation: EscalationLevel.Elevated,
                releasability: "NATO",
                countdownSeconds: 7f,
                isRecommended: true);

            Assert.That(coa.Id, Is.EqualTo("COA-X"));
            Assert.That(coa.IsRecommended, Is.True);
            Assert.That(coa.ExpectedLeakage.Point, Is.EqualTo(0.1f));
            Assert.That(coa.Escalation, Is.EqualTo(EscalationLevel.Elevated));
            Assert.That(coa.CountdownSeconds, Is.EqualTo(7f));
        }
    }
}
