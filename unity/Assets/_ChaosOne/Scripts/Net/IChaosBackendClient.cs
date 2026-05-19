using System.Threading;
using System.Threading.Tasks;
using ChaosOne.Decisions;

namespace ChaosOne.Net
{
    /// <summary>
    /// Abstraction over the chaos backend. Two implementations exist:
    ///   - ScriptedChaosBackendClient: in-process scripted streams, no network.
    ///   - GrpcChaosBackendClient: wraps generated gRPC stubs (M3+).
    /// The bootstrap selects one and registers it in the ServiceRegistry.
    /// </summary>
    public interface IChaosBackendClient
    {
        Task StartAsync(CancellationToken cancellationToken);
        Task StopAsync();
    }

    /// <summary>
    /// Optional capability surface for clients that can request a one-shot
    /// COA generation against the currently classified threat set.
    /// </summary>
    public interface ICourseOfActionGenerator
    {
        Task<CourseOfAction[]> GenerateAsync(string roeEnvelopeId, CancellationToken cancellationToken);
    }
}
