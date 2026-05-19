using System;
using System.Collections.Generic;

namespace ChaosOne.Core
{
    /// <summary>
    /// Strongly-typed synchronous publish/subscribe bus.
    /// Main-thread only; cross-thread publishers must marshal to the main thread upstream.
    /// </summary>
    public static class EventBus
    {
        private static readonly Dictionary<Type, Delegate> Handlers = new();

        public static void Subscribe<T>(Action<T> handler) where T : IChaosEvent
        {
            if (handler == null) throw new ArgumentNullException(nameof(handler));

            if (Handlers.TryGetValue(typeof(T), out var existing))
            {
                Handlers[typeof(T)] = Delegate.Combine(existing, handler);
            }
            else
            {
                Handlers[typeof(T)] = handler;
            }
        }

        public static void Unsubscribe<T>(Action<T> handler) where T : IChaosEvent
        {
            if (handler == null) throw new ArgumentNullException(nameof(handler));

            if (!Handlers.TryGetValue(typeof(T), out var existing)) return;

            var remaining = Delegate.Remove(existing, handler);
            if (remaining == null)
            {
                Handlers.Remove(typeof(T));
            }
            else
            {
                Handlers[typeof(T)] = remaining;
            }
        }

        public static void Publish<T>(T evt) where T : IChaosEvent
        {
            if (!Handlers.TryGetValue(typeof(T), out var existing)) return;

            if (existing is Action<T> typed)
            {
                typed(evt);
            }
        }

        public static void Clear()
        {
            Handlers.Clear();
        }
    }
}
