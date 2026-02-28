using Geodesic.App.DataLayer.Entities;
using Geodesic.App.Api.DataLoaders;
using HotChocolate;

namespace Geodesic.App.Api.Types;

[ExtendObjectType(typeof(WorkspaceMember))]
public sealed class WorkspaceMemberTypeExtensions
{
    /// <summary>
    /// Resolves the user for a workspace member via DataLoader (avoids N+1).
    /// </summary>
    public Task<User> UserAsync(
        [Parent] WorkspaceMember wm,
        UsersByIdLoader usersById,
        CancellationToken ct)
        => usersById.LoadAsync(wm.UserId, ct);
}
