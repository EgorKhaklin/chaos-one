using ChaosOne.Core;
using ChaosOne.Decisions;
using NUnit.Framework;
using UnityEngine;

namespace ChaosOne.Tests
{
    public sealed class COAQueueTests
    {
        private GameObject host;
        private COAQueue queue;

        [SetUp]
        public void SetUp()
        {
            EventBus.Clear();
            host = new GameObject("COAQueueHost");
            queue = host.AddComponent<COAQueue>();
        }

        [TearDown]
        public void TearDown()
        {
            if (host != null) Object.DestroyImmediate(host);
            EventBus.Clear();
        }

        private static CourseOfAction Coa(string id, bool isRecommended = false, float countdown = 10f) =>
            new(
                id: id,
                headline: $"{id} headline",
                whyOneLine: "why",
                expectedLeakage: new OutcomeBand(0.05f, 0.02f, 0.08f),
                cost: new MagazineDelta(ngi: 1),
                escalation: EscalationLevel.Low,
                releasability: "NATO",
                countdownSeconds: countdown,
                isRecommended: isRecommended);

        [Test]
        public void Propose_Publishes_COAProposed()
        {
            string seen = null;
            void Handler(COAProposed evt) => seen = evt.Coa.Id;
            EventBus.Subscribe<COAProposed>(Handler);

            queue.Propose(Coa("COA-X"));

            Assert.That(seen, Is.EqualTo("COA-X"));
            EventBus.Unsubscribe<COAProposed>(Handler);
        }

        [Test]
        public void Propose_Caps_Active_Set_At_Three()
        {
            queue.Propose(Coa("COA-A"));
            queue.Propose(Coa("COA-B"));
            queue.Propose(Coa("COA-C"));
            queue.Propose(Coa("COA-D")); // dropped by cap

            Assert.That(queue.ActiveCoas.Count, Is.EqualTo(3));
            CollectionAssert.AreEqual(
                new[] { "COA-A", "COA-B", "COA-C" },
                new[] { queue.ActiveCoas[0].Id, queue.ActiveCoas[1].Id, queue.ActiveCoas[2].Id });
        }

        [Test]
        public void Propose_Skips_Duplicate_Id()
        {
            queue.Propose(Coa("COA-A"));
            queue.Propose(Coa("COA-A"));

            Assert.That(queue.ActiveCoas.Count, Is.EqualTo(1));
        }

        [Test]
        public void Authorize_Removes_The_COA_And_Publishes_Event()
        {
            COAAuthorized? captured = null;
            void Handler(COAAuthorized evt) => captured = evt;
            EventBus.Subscribe<COAAuthorized>(Handler);

            queue.Propose(Coa("COA-A"));
            var ok = queue.Authorize("COA-A");

            Assert.That(ok, Is.True);
            Assert.That(queue.ActiveCoas.Count, Is.Zero);
            Assert.That(captured.HasValue, Is.True);
            Assert.That(captured.Value.Coa.Id, Is.EqualTo("COA-A"));
            Assert.That(captured.Value.Source, Is.EqualTo(AuthorizationSource.Operator));

            EventBus.Unsubscribe<COAAuthorized>(Handler);
        }

        [Test]
        public void Authorize_Unknown_Id_Returns_False()
        {
            Assert.That(queue.Authorize("ghost"), Is.False);
        }

        [Test]
        public void Object_Removes_The_COA_And_Publishes_With_Reason()
        {
            string reason = null;
            void Handler(COAObjected evt) => reason = evt.Reason;
            EventBus.Subscribe<COAObjected>(Handler);

            queue.Propose(Coa("COA-A"));
            var ok = queue.Object("COA-A", "operator dissent");

            Assert.That(ok, Is.True);
            Assert.That(reason, Is.EqualTo("operator dissent"));
            Assert.That(queue.ActiveCoas.Count, Is.Zero);

            EventBus.Unsubscribe<COAObjected>(Handler);
        }

        [Test]
        public void ClearAll_Publishes_Expired_For_Each_Active()
        {
            var expired = 0;
            void Handler(COAExpired _) => expired++;
            EventBus.Subscribe<COAExpired>(Handler);

            queue.Propose(Coa("COA-A"));
            queue.Propose(Coa("COA-B"));
            queue.ClearAll();

            Assert.That(expired, Is.EqualTo(2));
            Assert.That(queue.ActiveCoas.Count, Is.Zero);

            EventBus.Unsubscribe<COAExpired>(Handler);
        }

        [Test]
        public void ServiceRegistry_Holds_The_Queue_While_Live()
        {
            Assert.That(ServiceRegistry.TryResolve<COAQueue>(out var resolved), Is.True);
            Assert.That(resolved, Is.SameAs(queue));
        }
    }
}
