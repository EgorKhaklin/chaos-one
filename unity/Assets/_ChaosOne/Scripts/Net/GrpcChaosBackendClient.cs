using System.Threading;
using System.Threading.Tasks;
using ChaosOne.Decisions;

namespace ChaosOne.Net
{
    /// <summary>
    /// Wraps generated gRPC stubs (chaos_backend backend services).
    ///
    /// Activation requires:
    ///   1. Grpc.Net.Client + Grpc.Tools via NuGetForUnity
    ///      (https://github.com/GlitchEnzo/NuGetForUnity).
    ///   2. C# stubs generated from backend/proto/chaos_one.proto with
    ///      protoc + Grpc.Tools, dropped into Assets/_ChaosOne/Scripts/Net/Generated.
    ///   3. Add the generated namespace to ChaosOne.Runtime.asmdef references.
    ///
    /// Once the stubs land, replace the bodies below with real calls and add
    /// a streaming subscription that publishes COAProposed / ModeChanged into
    /// the EventBus as messages arrive.
    /// </summary>
    public sealed class GrpcChaosBackendClient : IChaosBackendClient, ICourseOfActionGenerator
    {
        private readonly string targetAddress;

        public GrpcChaosBackendClient(string targetAddress)
        {
            this.targetAddress = targetAddress;
        }

        public Task StartAsync(CancellationToken cancellationToken)
        {
            // var channel = GrpcChannel.ForAddress(targetAddress);
            // discrimination = new Discrimination.DiscriminationClient(channel);
            // coa = new CourseOfAction.CourseOfActionClient(channel);
            // adversary = new AdversaryModel.AdversaryModelClient(channel);
            // _ = SubscribeAdversaryStreamAsync(cancellationToken);
            UnityEngine.Debug.Log($"[grpc] would connect to {targetAddress}");
            return Task.CompletedTask;
        }

        public Task StopAsync()
        {
            // channel?.Dispose();
            return Task.CompletedTask;
        }

        public Task<CourseOfAction[]> GenerateAsync(string roeEnvelopeId, CancellationToken cancellationToken)
        {
            // var request = new COARequest { RoeEnvelopeId = roeEnvelopeId };
            // var response = await coa.GenerateAsync(request, cancellationToken: cancellationToken);
            // return MapBundle(response);
            return Task.FromResult(System.Array.Empty<CourseOfAction>());
        }
    }
}
