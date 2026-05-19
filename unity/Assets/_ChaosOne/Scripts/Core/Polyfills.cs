// .NET Standard 2.1 (Unity's target) ships without
// System.Runtime.CompilerServices.IsExternalInit, which C# 10's record
// types require for their `init` accessors. Re-declaring the type
// in user code is the documented polyfill — once the runtime gets it,
// our copy becomes unused but harmless.

namespace System.Runtime.CompilerServices
{
    // public so the type is visible to the Editor and Tests assemblies that
    // reference ChaosOne.Runtime; the compiler needs to resolve it for any
    // `init` accessor in records compiled in those assemblies.
    public static class IsExternalInit
    {
    }
}
