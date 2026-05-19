using System.Threading;
using System.Threading.Tasks;
using ChaosOne.Decisions;

namespace ChaosOne.Net
{
    /// <summary>
    /// In-process scripted client. Returns canned COA bundles synchronously
    /// for the front-end. Continuous adversary updates are published by
    /// the companion ScriptedFeed MonoBehaviour, which the BackendBootstrap
    /// attaches alongside this client whenever Scripted mode is selected.
    /// </summary>
    public sealed class ScriptedChaosBackendClient : IChaosBackendClient, ICourseOfActionGenerator
    {
        public Task StartAsync(CancellationToken cancellationToken) => Task.CompletedTask;

        public Task StopAsync() => Task.CompletedTask;

        public Task<CourseOfAction[]> GenerateAsync(string roeEnvelopeId, CancellationToken cancellationToken)
        {
            var bundle = new CourseOfAction[]
            {
                new(
                    id: "COA-A",
                    headline: "Pure kinetic engagement",
                    whyOneLine: "NGI on confirmed midcourse threats. No directed-energy or non-kinetic.",
                    expectedLeakage: new OutcomeBand(0.07f, 0.03f, 0.11f),
                    cost: new MagazineDelta(ngi: 4),
                    escalation: EscalationLevel.Moderate,
                    releasability: roeEnvelopeId,
                    countdownSeconds: 10f,
                    isRecommended: false),
                new(
                    id: "COA-B",
                    headline: "Mixed engagement",
                    whyOneLine: "NGI on highest-confidence. HEL on swarm. Cyber denial of adversary GNSS guidance.",
                    expectedLeakage: new OutcomeBand(0.05f, 0.02f, 0.08f),
                    cost: new MagazineDelta(ngi: 2, helMegajoules: 1.2f),
                    escalation: EscalationLevel.Low,
                    releasability: roeEnvelopeId,
                    countdownSeconds: 8f,
                    isRecommended: true),
                new(
                    id: "COA-C",
                    headline: "Conservative reserve",
                    whyOneLine: "Engage two threats now; reserve magazine for projected Wave-2 launch.",
                    expectedLeakage: new OutcomeBand(0.11f, 0.06f, 0.17f),
                    cost: new MagazineDelta(ngi: 2),
                    escalation: EscalationLevel.Low,
                    releasability: roeEnvelopeId,
                    countdownSeconds: 12f,
                    isRecommended: false),
            };
            return Task.FromResult(bundle);
        }
    }
}
