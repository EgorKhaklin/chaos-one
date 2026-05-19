using ChaosOne.Core;
using NUnit.Framework;

namespace ChaosOne.Tests
{
    public sealed class EventBusTests
    {
        private readonly record struct PingEvent(int Value) : IChaosEvent;
        private readonly record struct OtherEvent(string Tag) : IChaosEvent;

        [SetUp]
        public void Reset() => EventBus.Clear();

        [Test]
        public void Publish_Reaches_Subscriber()
        {
            var received = 0;
            void Handler(PingEvent evt) => received = evt.Value;

            EventBus.Subscribe<PingEvent>(Handler);
            EventBus.Publish(new PingEvent(42));

            Assert.That(received, Is.EqualTo(42));
        }

        [Test]
        public void Publish_With_No_Subscriber_Is_NoOp()
        {
            Assert.DoesNotThrow(() => EventBus.Publish(new PingEvent(1)));
        }

        [Test]
        public void Multiple_Subscribers_All_Receive()
        {
            var calls = 0;
            EventBus.Subscribe<PingEvent>(_ => calls++);
            EventBus.Subscribe<PingEvent>(_ => calls++);
            EventBus.Publish(new PingEvent(0));

            Assert.That(calls, Is.EqualTo(2));
        }

        [Test]
        public void Unsubscribe_Removes_Specific_Handler()
        {
            var first = 0;
            var second = 0;
            void HandlerA(PingEvent _) => first++;
            void HandlerB(PingEvent _) => second++;

            EventBus.Subscribe<PingEvent>(HandlerA);
            EventBus.Subscribe<PingEvent>(HandlerB);
            EventBus.Unsubscribe<PingEvent>(HandlerA);
            EventBus.Publish(new PingEvent(0));

            Assert.That(first, Is.Zero);
            Assert.That(second, Is.EqualTo(1));
        }

        [Test]
        public void Different_Event_Types_Are_Isolated()
        {
            var pings = 0;
            var others = 0;
            EventBus.Subscribe<PingEvent>(_ => pings++);
            EventBus.Subscribe<OtherEvent>(_ => others++);

            EventBus.Publish(new PingEvent(0));

            Assert.That(pings, Is.EqualTo(1));
            Assert.That(others, Is.Zero);
        }
    }
}
