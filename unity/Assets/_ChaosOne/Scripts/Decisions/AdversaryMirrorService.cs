using System.Collections.Generic;
using ChaosOne.Core;
using UnityEngine;

namespace ChaosOne.Decisions
{
    /// <summary>
    /// Holds the latest adversary distribution and a rolling window of
    /// cost-imposition samples for the sparkline. Updated by the backend
    /// client; read by the AdversaryMirror UI.
    /// </summary>
    public sealed class AdversaryMirrorService : MonoBehaviour
    {
        [SerializeField] private int costImpositionHistoryCapacity = 24;

        private readonly Queue<float> costImpositionHistory = new();

        public AdversaryDistribution LatestDistribution { get; private set; }

        public IReadOnlyCollection<float> CostImpositionHistory => costImpositionHistory;

        private void Awake()
        {
            ServiceRegistry.Register(this);
        }

        private void OnEnable()
        {
            EventBus.Subscribe<AdversaryPlaybookUpdated>(OnPlaybookUpdated);
        }

        private void OnDisable()
        {
            EventBus.Unsubscribe<AdversaryPlaybookUpdated>(OnPlaybookUpdated);
        }

        private void OnDestroy()
        {
            ServiceRegistry.Unregister<AdversaryMirrorService>();
        }

        private void OnPlaybookUpdated(AdversaryPlaybookUpdated evt)
        {
            LatestDistribution = evt.Distribution;
            PushCostImposition(evt.Distribution.CostImpositionIndex);
            EventBus.Publish(new CostImpositionSampled(
                evt.Distribution.TimestampSeconds,
                evt.Distribution.CostImpositionIndex));
        }

        private void PushCostImposition(float value)
        {
            costImpositionHistory.Enqueue(value);
            while (costImpositionHistory.Count > costImpositionHistoryCapacity)
            {
                costImpositionHistory.Dequeue();
            }
        }
    }
}
