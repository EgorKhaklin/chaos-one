using System.Collections.Generic;
using ChaosOne.Core;
using ChaosOne.Decisions;
using UnityEngine;

namespace ChaosOne.Net
{
    /// <summary>
    /// Main-thread MonoBehaviour that emits the periodic events a real
    /// backend would push: adversary playbook distribution updates, cost
    /// imposition samples. Spawned by BackendBootstrap when the chosen
    /// backend mode is Scripted. Separated from ScriptedChaosBackendClient
    /// because EventBus.Publish is main-thread-only.
    /// </summary>
    public sealed class ScriptedFeed : MonoBehaviour
    {
        [SerializeField] private float intervalSeconds = 0.5f;

        private float accumulator;
        private float driftPhase;

        private void Update()
        {
            accumulator += Time.deltaTime;
            if (accumulator < intervalSeconds) return;
            accumulator = 0f;
            driftPhase += intervalSeconds;

            PublishPlaybookUpdate();
        }

        private void PublishPlaybookUpdate()
        {
            var oscillation = (Mathf.Sin(driftPhase * 0.05f) + 1f) * 0.5f;

            var charlie7Weight = 0.55f + 0.15f * oscillation;
            var bravo3Weight = 0.30f - 0.10f * oscillation;
            var unknownWeight = Mathf.Max(0f, 1f - charlie7Weight - bravo3Weight);

            var hypotheses = new List<PlaybookHypothesis>
            {
                new(
                    "charlie-7",
                    "Charlie-7 saturation HGV + decoy cloud",
                    charlie7Weight,
                    0.10f * Mathf.Cos(driftPhase * 0.05f)),
                new(
                    "bravo-3",
                    "Bravo-3 probe, no follow-on",
                    bravo3Weight,
                    -0.06f * Mathf.Cos(driftPhase * 0.05f)),
                new(
                    "unknown",
                    "Off-distribution / unknown",
                    unknownWeight,
                    0f),
            };

            var costImposition = 1.10f + 0.08f * Mathf.Sin(driftPhase * 0.02f);

            var distribution = new AdversaryDistribution(
                timestampSeconds: Time.timeAsDouble,
                hypotheses: hypotheses,
                costImpositionIndex: costImposition);

            EventBus.Publish(new AdversaryPlaybookUpdated(distribution));
        }
    }
}
