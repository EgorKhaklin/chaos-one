using System;
using System.Collections.Generic;

namespace ChaosOne.Core
{
    /// <summary>
    /// Minimal service locator. Register concrete services at scene boot;
    /// consumers resolve by interface type. Intentionally simpler than a
    /// full DI container; trade composability for fewer indirections.
    /// </summary>
    public static class ServiceRegistry
    {
        private static readonly Dictionary<Type, object> Services = new();

        public static void Register<T>(T instance) where T : class
        {
            if (instance == null) throw new ArgumentNullException(nameof(instance));
            Services[typeof(T)] = instance;
        }

        public static bool TryResolve<T>(out T instance) where T : class
        {
            if (Services.TryGetValue(typeof(T), out var raw) && raw is T cast)
            {
                instance = cast;
                return true;
            }

            instance = null;
            return false;
        }

        public static T Resolve<T>() where T : class
        {
            if (!TryResolve<T>(out var instance))
            {
                throw new InvalidOperationException($"Service not registered: {typeof(T).FullName}");
            }
            return instance;
        }

        public static void Unregister<T>() where T : class
        {
            Services.Remove(typeof(T));
        }

        public static void Clear()
        {
            Services.Clear();
        }
    }
}
