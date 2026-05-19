using ChaosOne.Core;
using UnityEngine;

namespace ChaosOne.Decisions
{
    /// <summary>
    /// Owns the system's OperationalMode. Mode changes publish a ModeChanged
    /// event so the Mode HUD and any other subscribers can react. Register
    /// the live instance in the ServiceRegistry at scene boot.
    /// </summary>
    public sealed class ModeStateMachine : MonoBehaviour
    {
        [SerializeField] private OperationalMode initialMode = OperationalMode.Nominal;

        public OperationalMode Current { get; private set; }

        private void Awake()
        {
            Current = initialMode;
            ServiceRegistry.Register(this);
        }

        private void OnDestroy()
        {
            ServiceRegistry.Unregister<ModeStateMachine>();
        }

        public void Transition(OperationalMode next)
        {
            if (Current == next) return;
            var previous = Current;
            Current = next;
            EventBus.Publish(new ModeChanged(previous, next));
        }
    }
}
