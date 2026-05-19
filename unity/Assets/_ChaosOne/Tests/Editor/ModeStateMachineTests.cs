using ChaosOne.Core;
using ChaosOne.Decisions;
using NUnit.Framework;
using UnityEngine;

namespace ChaosOne.Tests
{
    public sealed class ModeStateMachineTests
    {
        private GameObject host;
        private ModeStateMachine machine;

        [SetUp]
        public void SetUp()
        {
            EventBus.Clear();
            host = new GameObject("ModeStateMachineHost");
            machine = host.AddComponent<ModeStateMachine>();
        }

        [TearDown]
        public void TearDown()
        {
            if (host != null) Object.DestroyImmediate(host);
            EventBus.Clear();
        }

        [Test]
        public void Initial_State_Is_Nominal()
        {
            Assert.That(machine.Current, Is.EqualTo(OperationalMode.Nominal));
        }

        [Test]
        public void Transition_Publishes_ModeChanged_With_Previous_And_Current()
        {
            ModeChanged? captured = null;
            void Handler(ModeChanged evt) => captured = evt;
            EventBus.Subscribe<ModeChanged>(Handler);

            machine.Transition(OperationalMode.SensorDegraded);

            Assert.That(captured.HasValue, Is.True);
            Assert.That(captured.Value.Previous, Is.EqualTo(OperationalMode.Nominal));
            Assert.That(captured.Value.Current, Is.EqualTo(OperationalMode.SensorDegraded));
            Assert.That(machine.Current, Is.EqualTo(OperationalMode.SensorDegraded));

            EventBus.Unsubscribe<ModeChanged>(Handler);
        }

        [Test]
        public void Transition_To_Same_State_Is_NoOp()
        {
            var fired = 0;
            void Handler(ModeChanged _) => fired++;
            EventBus.Subscribe<ModeChanged>(Handler);

            machine.Transition(OperationalMode.Nominal);

            Assert.That(fired, Is.Zero);
            EventBus.Unsubscribe<ModeChanged>(Handler);
        }

        [Test]
        public void Registers_Itself_In_ServiceRegistry()
        {
            Assert.That(ServiceRegistry.TryResolve<ModeStateMachine>(out var resolved), Is.True);
            Assert.That(resolved, Is.SameAs(machine));
        }
    }
}
