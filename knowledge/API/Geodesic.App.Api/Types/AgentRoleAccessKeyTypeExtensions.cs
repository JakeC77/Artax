using Geodesic.App.DataLayer.Entities;
using HotChocolate.Types;

namespace Geodesic.App.Api.Types;

[ExtendObjectType(typeof(AgentRoleAccessKey), IgnoreProperties = new[] { nameof(AgentRoleAccessKey.KeyHash) })]
public sealed class AgentRoleAccessKeyTypeExtensions
{
}
