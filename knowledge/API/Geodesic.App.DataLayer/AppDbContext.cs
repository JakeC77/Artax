using Microsoft.EntityFrameworkCore;

namespace Geodesic.App.DataLayer;

public class AppDbContext : DbContext
{
    public AppDbContext(DbContextOptions<AppDbContext> options) : base(options) {}

    public DbSet<Entities.Tenant> Tenants => Set<Entities.Tenant>();
    public DbSet<Entities.Role> Roles => Set<Entities.Role>();
    public DbSet<Entities.User> Users => Set<Entities.User>();
    public DbSet<Entities.UserRole> UserRoles => Set<Entities.UserRole>();

    public DbSet<Entities.Workspace> Workspaces => Set<Entities.Workspace>();
    public DbSet<Entities.WorkspaceMember> WorkspaceMembers => Set<Entities.WorkspaceMember>();
    public DbSet<Entities.WorkspaceItem> WorkspaceItems => Set<Entities.WorkspaceItem>();

    public DbSet<Entities.OverlayChangeset> OverlayChangesets => Set<Entities.OverlayChangeset>();
    public DbSet<Entities.OverlayNodePatch> OverlayNodePatches => Set<Entities.OverlayNodePatch>();
    public DbSet<Entities.OverlayEdgePatch> OverlayEdgePatches => Set<Entities.OverlayEdgePatch>();

    public DbSet<Entities.Scenario> Scenarios => Set<Entities.Scenario>();
    public DbSet<Entities.ScenarioRun> ScenarioRuns => Set<Entities.ScenarioRun>();
    public DbSet<Entities.ScenarioRunLog> ScenarioRunLogs => Set<Entities.ScenarioRunLog>();
    public DbSet<Entities.FeedbackRequest> FeedbackRequests => Set<Entities.FeedbackRequest>();
    public DbSet<Entities.Feedback> Feedbacks => Set<Entities.Feedback>();

    public DbSet<Entities.Insight> Insights => Set<Entities.Insight>();
    public DbSet<Entities.AnswerableQuestion> AnswerableQuestions => Set<Entities.AnswerableQuestion>();
    public DbSet<Entities.AITeam> AITeams => Set<Entities.AITeam>();
    public DbSet<Entities.AITeamMember> AITeamMembers => Set<Entities.AITeamMember>();
    public DbSet<Entities.WorkspaceAnalysis> WorkspaceAnalyses => Set<Entities.WorkspaceAnalysis>();
    public DbSet<Entities.WorkspaceAnalysisMetric> WorkspaceAnalysisMetrics => Set<Entities.WorkspaceAnalysisMetric>();
    public DbSet<Entities.ScenarioMetric> ScenarioMetrics => Set<Entities.ScenarioMetric>();
    public DbSet<Entities.ScratchpadAttachment> ScratchpadAttachments => Set<Entities.ScratchpadAttachment>();
    public DbSet<Entities.ScratchpadNote> ScratchpadNotes => Set<Entities.ScratchpadNote>();
    public DbSet<Entities.SemanticEntity> SemanticEntities => Set<Entities.SemanticEntity>();
    public DbSet<Entities.SemanticField> SemanticFields => Set<Entities.SemanticField>();

    public DbSet<Entities.ReportTemplate> ReportTemplates => Set<Entities.ReportTemplate>();
    public DbSet<Entities.ReportTemplateSection> ReportTemplateSections => Set<Entities.ReportTemplateSection>();
    public DbSet<Entities.ReportTemplateBlock> ReportTemplateBlocks => Set<Entities.ReportTemplateBlock>();
    public DbSet<Entities.Report> Reports => Set<Entities.Report>();
    public DbSet<Entities.ReportSection> ReportSections => Set<Entities.ReportSection>();
    public DbSet<Entities.ReportBlock> ReportBlocks => Set<Entities.ReportBlock>();
    public DbSet<Entities.ReportBlockRichText> ReportBlockRichTexts => Set<Entities.ReportBlockRichText>();
    public DbSet<Entities.ReportBlockSingleMetric> ReportBlockSingleMetrics => Set<Entities.ReportBlockSingleMetric>();
    public DbSet<Entities.ReportBlockMultiMetric> ReportBlockMultiMetrics => Set<Entities.ReportBlockMultiMetric>();
    public DbSet<Entities.ReportBlockInsightCard> ReportBlockInsightCards => Set<Entities.ReportBlockInsightCard>();
    public DbSet<Entities.Source> Sources => Set<Entities.Source>();
    public DbSet<Entities.Ontology> Ontologies => Set<Entities.Ontology>();
    public DbSet<Entities.Company> Companies => Set<Entities.Company>();
    public DbSet<Entities.DataLoadingAttachment> DataLoadingAttachments => Set<Entities.DataLoadingAttachment>();
    public DbSet<Entities.Intent> Intents => Set<Entities.Intent>();
    public DbSet<Entities.AgentRole> AgentRoles => Set<Entities.AgentRole>();
    public DbSet<Entities.AgentRoleIntent> AgentRoleIntents => Set<Entities.AgentRoleIntent>();
    public DbSet<Entities.AgentRoleAccessKey> AgentRoleAccessKeys => Set<Entities.AgentRoleAccessKey>();

    protected override void OnModelCreating(ModelBuilder b)
    {
        b.HasDefaultSchema("app");
      //  b.HasPostgresExtension("citext");
        b.UseIdentityByDefaultColumns();
        // Naming convention is configured on DbContextOptionsBuilder in Program.cs

        // Tenants
        b.Entity<Entities.Tenant>(e => {
            e.ToTable("tenants");
            e.HasKey(x => x.TenantId);
            e.Property(x => x.Name).IsRequired();
            e.Property(x => x.Region).HasDefaultValue("us");
            e.Property(x => x.CreatedAt).HasDefaultValueSql("now()");
        });

        // Roles
        b.Entity<Entities.Role>(e => {
            e.ToTable("roles");
            e.HasKey(x => new { x.TenantId, x.RoleName });
            e.Property(x => x.RoleName).IsRequired();
        });

        // Users
        b.Entity<Entities.User>(e => {
            e.ToTable("users");
            e.HasKey(x => x.UserId);
            e.HasIndex(x => new { x.TenantId, x.Email }).IsUnique();
            e.HasIndex(x => new { x.TenantId, x.Subject }).IsUnique();
            e.Property(x => x.Preferences).HasColumnType("jsonb").HasDefaultValueSql("'{}'::jsonb");
            e.Property(x => x.CreatedAt).HasDefaultValueSql("now()");
            e.Property(x => x.UpdatedAt).HasDefaultValueSql("now()");
        });

        // UserRoles
        b.Entity<Entities.UserRole>(e => {
            e.ToTable("user_roles");
            e.HasKey(x => new { x.UserId, x.RoleName });
        });

        // Workspaces
        b.Entity<Entities.Workspace>(e => {
            e.ToTable("workspaces");
            e.HasKey(x => x.WorkspaceId);
            e.HasIndex(x => x.TenantId);
            e.HasIndex(x => x.CompanyId);
            e.HasIndex(x => x.OntologyId);
            e.HasIndex(x => new { x.TenantId, x.Name });
            e.Property(x => x.Visibility).HasDefaultValue("private");
            e.Property(x => x.State).HasDefaultValue("draft");
            e.Property(x => x.SetupStage).HasDefaultValue("intent_discovery");
            e.Property(x => x.SetupIntentPackage).HasColumnType("jsonb");
            e.Property(x => x.SetupDataScope).HasColumnType("jsonb");
            e.Property(x => x.SetupExecutionResults).HasColumnType("jsonb");
            e.Property(x => x.SetupTeamConfig).HasColumnType("jsonb");
            e.Property(x => x.CreatedAt).HasDefaultValueSql("now()");
            e.Property(x => x.UpdatedAt).HasDefaultValueSql("now()");
        });

        // WorkspaceMembers
        b.Entity<Entities.WorkspaceMember>(e => {
            e.ToTable("workspace_members");
            e.HasKey(x => new { x.WorkspaceId, x.UserId });
            e.Property(x => x.Role).HasDefaultValue("viewer");
            e.Property(x => x.AddedAt).HasDefaultValueSql("now()");
        });

        // WorkspaceItems
        b.Entity<Entities.WorkspaceItem>(e => {
            e.ToTable("workspace_items");
            e.HasKey(x => x.WorkspaceItemId);
            e.HasIndex(x => new { x.WorkspaceId, x.GraphNodeId, x.GraphEdgeId }).IsUnique();
            e.Property(x => x.Labels).HasColumnType("text[]").HasDefaultValueSql("'{}'::text[]");
            e.Property(x => x.PinnedAt).HasDefaultValueSql("now()");
        });

        // OverlayChangeset
        b.Entity<Entities.OverlayChangeset>(e => {
            e.ToTable("overlay_changesets");
            e.HasKey(x => x.ChangesetId);
            e.Property(x => x.Status).HasDefaultValue("draft");
            e.Property(x => x.CreatedAt).HasDefaultValueSql("now()");
            e.Property(x => x.UpdatedAt).HasDefaultValueSql("now()");
        });

        // OverlayNodePatch
        b.Entity<Entities.OverlayNodePatch>(e => {
            e.ToTable("overlay_node_patch");
            e.HasKey(x => new { x.ChangesetId, x.GraphNodeId });
            e.Property(x => x.Op).HasDefaultValue("upsert");
            e.Property(x => x.Patch).HasColumnType("jsonb").HasDefaultValueSql("'{}'::jsonb");
        });

        // OverlayEdgePatch
        b.Entity<Entities.OverlayEdgePatch>(e => {
            e.ToTable("overlay_edge_patch");
            e.HasKey(x => new { x.ChangesetId, x.GraphEdgeId });
            e.Property(x => x.Op).HasDefaultValue("upsert");
            e.Property(x => x.Patch).HasColumnType("jsonb").HasDefaultValueSql("'{}'::jsonb");
        });

        // Scenarios
        b.Entity<Entities.Scenario>(e => {
            e.ToTable("scenarios");
            e.HasKey(x => x.ScenarioId);
            e.HasIndex(x => new { x.WorkspaceId, x.Name }).IsUnique();
            e.Property(x => x.CreatedAt).HasDefaultValueSql("now()");
        });

        // ScenarioRuns
        b.Entity<Entities.ScenarioRun>(e => {
            e.ToTable("scenario_runs");
            e.HasKey(x => x.RunId);
            e.HasIndex(x => x.WorkspaceId);
            e.Property(x => x.Status).HasDefaultValue("queued");
        });

        // ScenarioRunLogs
        b.Entity<Entities.ScenarioRunLog>(e => {
            e.ToTable("scenario_run_logs");
            e.HasKey(x => x.LogId);
            e.Property(x => x.CreatedAt).HasDefaultValueSql("now()");
        });

        // FeedbackRequests
        b.Entity<Entities.FeedbackRequest>(e => {
            e.ToTable("feedback_requests");
            e.HasKey(x => x.FeedbackRequestId);
            e.HasIndex(x => new { x.RunId, x.IsResolved });
            e.Property(x => x.Checkpoint).IsRequired();
            e.Property(x => x.Message).IsRequired();
            e.Property(x => x.Options).HasColumnType("text[]").HasDefaultValueSql("'{}'::text[]");
            e.Property(x => x.Metadata).HasColumnType("jsonb").HasDefaultValueSql("'{}'::jsonb");
            e.Property(x => x.CreatedAt).HasDefaultValueSql("now()");
            e.Property(x => x.TimeoutSeconds).HasDefaultValue(300);
            e.Property(x => x.IsResolved).HasDefaultValue(false);
        });

        // Feedbacks
        b.Entity<Entities.Feedback>(e => {
            e.ToTable("feedbacks");
            e.HasKey(x => x.FeedbackId);
            e.HasIndex(x => x.RunId);
            e.Property(x => x.FeedbackText).IsRequired();
            e.Property(x => x.Action).IsRequired();
            e.Property(x => x.Target).HasColumnType("jsonb").HasDefaultValueSql("'{}'::jsonb");
            e.Property(x => x.Timestamp).HasDefaultValueSql("now()");
            e.Property(x => x.Applied).HasDefaultValue(false);
        });

        // Insights
        b.Entity<Entities.Insight>(e => {
            e.ToTable("insights");
            e.HasKey(x => x.InsightId);
            e.Property(x => x.RelatedGraphIds).HasColumnType("text[]").HasDefaultValueSql("'{}'::text[]");
            e.Property(x => x.EvidenceRefs).HasColumnType("jsonb").HasDefaultValueSql("'[]'::jsonb");
            e.Property(x => x.GeneratedAt).HasDefaultValueSql("now()");
        });

        // AnswerableQuestions
        b.Entity<Entities.AnswerableQuestion>(e => {
            e.ToTable("answerable_questions");
            e.HasKey(x => x.AnswerableQuestionId);
            e.Property(x => x.Question).IsRequired();
            e.Property(x => x.Query).IsRequired();
            e.Property(x => x.ResultPlaybook).IsRequired();
            e.Property(x => x.RequiredVariables).HasColumnType("text[]").HasDefaultValueSql("'{}'::text[]");
        });

        // AITeams
        b.Entity<Entities.AITeam>(e => {
            e.ToTable("ai_teams");
            e.HasKey(x => x.AITeamId);
            e.HasIndex(x => x.WorkspaceId).IsUnique();
            e.Property(x => x.Name).IsRequired();
            e.Property(x => x.CreatedAt).HasDefaultValueSql("now()");
            e.Property(x => x.UpdatedAt).HasDefaultValueSql("now()");

            e.HasOne<Entities.Workspace>()
                .WithOne()
                .HasForeignKey<Entities.AITeam>(x => x.WorkspaceId)
                .OnDelete(DeleteBehavior.Cascade);
        });

        // AITeamMembers
        b.Entity<Entities.AITeamMember>(e => {
            e.ToTable("ai_team_members");
            e.HasKey(x => x.AITeamMemberId);
            e.HasIndex(x => new { x.AITeamId, x.AgentId }).IsUnique();
            e.Property(x => x.AgentId).IsRequired();
            e.Property(x => x.Name).IsRequired();
            e.Property(x => x.Role).IsRequired();
            e.Property(x => x.SystemPrompt).HasColumnType("text");
            e.Property(x => x.Tools).HasColumnType("text[]").HasDefaultValueSql("'{}'::text[]");
            e.Property(x => x.Expertise).HasColumnType("text[]").HasDefaultValueSql("'{}'::text[]");
            e.Property(x => x.CreatedAt).HasDefaultValueSql("now()");
            e.Property(x => x.UpdatedAt).HasDefaultValueSql("now()");
            e.HasOne(x => x.Team)
                .WithMany(x => x.Members)
                .HasForeignKey(x => x.AITeamId)
                .OnDelete(DeleteBehavior.Cascade);
        });

        // WorkspaceAnalyses
        b.Entity<Entities.WorkspaceAnalysis>(e => {
            e.ToTable("workspace_analyses");
            e.HasKey(x => x.WorkspaceAnalysisId);
            e.Property(x => x.TitleText).IsRequired();
            e.Property(x => x.CreatedOn).HasDefaultValueSql("now()");
            e.Property(x => x.Version).HasDefaultValue(1);
        });

        // WorkspaceAnalysisMetrics
        b.Entity<Entities.WorkspaceAnalysisMetric>(e => {
            e.ToTable("workspace_analysis_metrics");
            e.HasKey(x => x.WorkspaceAnalysisMetricId);
            e.Property(x => x.CreatedOn).HasDefaultValueSql("now()");
        });

        // ScenarioMetrics
        b.Entity<Entities.ScenarioMetric>(e => {
            e.ToTable("scenario_metrics");
            e.HasKey(x => x.ScenarioMetricId);
            e.Property(x => x.CreatedOn).HasDefaultValueSql("now()");
            e.Property(x => x.Version).HasDefaultValue(1);
        });

        // ScratchpadAttachments
        b.Entity<Entities.ScratchpadAttachment>(e => {
            e.ToTable("scratchpad_attachments");
            e.HasKey(x => x.ScratchpadAttachmentId);
            e.HasIndex(x => x.WorkspaceId);
            e.Property(x => x.CreatedOn).HasDefaultValueSql("now()");
        });

        // ScratchpadNotes
        b.Entity<Entities.ScratchpadNote>(e => {
            e.ToTable("scratchpad_notes");
            e.HasKey(x => x.ScratchpadNoteId);
            e.HasIndex(x => x.WorkspaceId);
            e.Property(x => x.CreatedOn).HasDefaultValueSql("now()");
        });

        // Ontologies (tenant-scoped; shared across workspaces)
        b.Entity<Entities.Ontology>(e => {
            e.ToTable("ontologies");
            e.HasKey(x => x.OntologyId);
            e.HasIndex(x => x.TenantId);
            e.HasIndex(x => x.CompanyId);
            e.Property(x => x.Name).IsRequired();
            e.Property(x => x.Status).HasDefaultValue("draft");
            e.Property(x => x.CreatedOn).HasDefaultValueSql("now()");
            e.Property(x => x.DomainExamples).HasColumnType("text");
        });

        // Companies (tenant-scoped; name + markdown for agentic workflows)
        b.Entity<Entities.Company>(e => {
            e.ToTable("companies");
            e.HasKey(x => x.CompanyId);
            e.HasIndex(x => x.TenantId);
            e.Property(x => x.Name).IsRequired();
            e.Property(x => x.MarkdownContent).HasColumnType("text");
        });

        // Intents (tenant-scoped; agent intent operations: input/output schema, grounding; optional ontology)
        b.Entity<Entities.Intent>(e => {
            e.ToTable("intents");
            e.HasKey(x => x.IntentId);
            e.HasIndex(x => x.TenantId);
            e.HasIndex(x => x.OntologyId);
            e.HasIndex(x => new { x.TenantId, x.OpId }).IsUnique();
            e.Property(x => x.OpId).IsRequired();
            e.Property(x => x.IntentName).IsRequired();
            e.Property(x => x.InputSchema).HasColumnType("jsonb");
            e.Property(x => x.OutputSchema).HasColumnType("jsonb");
            e.Property(x => x.Grounding).HasColumnType("text");
            e.Property(x => x.CreatedOn).HasDefaultValueSql("now()");
            e.HasOne<Entities.Ontology>().WithMany().HasForeignKey(x => x.OntologyId).IsRequired(false);
        });

        // AgentRoles (tenant-scoped; read/write ontology + allowed intents)
        b.Entity<Entities.AgentRole>(e => {
            e.ToTable("agent_roles");
            e.HasKey(x => x.AgentRoleId);
            e.HasIndex(x => x.TenantId);
            e.HasIndex(x => x.ReadOntologyId);
            e.HasIndex(x => x.WriteOntologyId);
            e.HasIndex(x => new { x.TenantId, x.Name }).IsUnique();
            e.Property(x => x.Name).IsRequired();
            e.Property(x => x.CreatedOn).HasDefaultValueSql("now()");
            e.HasOne<Entities.Ontology>().WithMany().HasForeignKey(x => x.ReadOntologyId).IsRequired(false);
            e.HasOne<Entities.Ontology>().WithMany().HasForeignKey(x => x.WriteOntologyId).IsRequired(false);
        });

        // AgentRoleIntent (many-to-many: role -> intents allowed)
        b.Entity<Entities.AgentRoleIntent>(e => {
            e.ToTable("agent_role_intents");
            e.HasKey(x => new { x.AgentRoleId, x.IntentId });
            e.HasIndex(x => x.IntentId);
            e.HasOne<Entities.AgentRole>().WithMany().HasForeignKey(x => x.AgentRoleId).OnDelete(DeleteBehavior.Cascade);
            e.HasOne<Entities.Intent>().WithMany().HasForeignKey(x => x.IntentId).OnDelete(DeleteBehavior.Cascade);
        });

        // AgentRoleAccessKey (keys for a role; store hash + prefix only)
        b.Entity<Entities.AgentRoleAccessKey>(e => {
            e.ToTable("agent_role_access_keys");
            e.HasKey(x => x.AccessKeyId);
            e.HasIndex(x => x.AgentRoleId);
            e.HasIndex(x => x.KeyHash).IsUnique();
            e.Property(x => x.KeyHash).IsRequired();
            e.Property(x => x.KeyPrefix).IsRequired();
            e.Property(x => x.CreatedOn).HasDefaultValueSql("now()");
            e.HasOne<Entities.AgentRole>().WithMany().HasForeignKey(x => x.AgentRoleId).OnDelete(DeleteBehavior.Cascade);
        });

        // DataLoadingAttachments (CSV uploads per ontology for data-loading workflow)
        b.Entity<Entities.DataLoadingAttachment>(e => {
            e.ToTable("data_loading_attachments");
            e.HasKey(x => x.AttachmentId);
            e.HasIndex(x => x.TenantId);
            e.HasIndex(x => x.OntologyId);
            e.Property(x => x.FileName).IsRequired();
            e.Property(x => x.BlobPath).IsRequired();
            e.Property(x => x.Status).HasDefaultValue("uploaded");
            e.Property(x => x.CreatedOn).HasDefaultValueSql("now()");
        });

        // SemanticEntities
        b.Entity<Entities.SemanticEntity>(e => {
            e.ToTable("semantic_entities");
            e.HasKey(x => x.SemanticEntityId);
            e.HasIndex(x => x.OntologyId);
            e.HasIndex(x => new { x.OntologyId, x.NodeLabel }).IsUnique().HasFilter("ontology_id IS NOT NULL");
            e.Property(x => x.NodeLabel).IsRequired();
            e.Property(x => x.Name).IsRequired();
            e.Property(x => x.Version).HasDefaultValue(1);
            e.Property(x => x.CreatedOn).HasDefaultValueSql("now()");
            e.HasOne<Entities.Ontology>().WithMany().HasForeignKey(x => x.OntologyId).IsRequired(false).OnDelete(DeleteBehavior.SetNull);
        });

        // SemanticFields
        b.Entity<Entities.SemanticField>(e => {
            e.ToTable("semantic_fields");
            e.HasKey(x => x.SemanticFieldId);
            e.HasIndex(x => x.SemanticEntityId);
            e.HasIndex(x => new { x.SemanticEntityId, x.Name, x.Version }).IsUnique();
            e.Property(x => x.Name).IsRequired();
            e.Property(x => x.Version).HasDefaultValue(1);
            e.Property(x => x.RangeInfo).HasColumnType("jsonb");
            e.HasOne(x => x.SemanticEntity)
                .WithMany(x => x.Fields)
                .HasForeignKey(x => x.SemanticEntityId)
                .OnDelete(DeleteBehavior.Cascade);
        });

        // ReportTemplates
        b.Entity<Entities.ReportTemplate>(e => {
            e.ToTable("report_templates");
            e.HasKey(x => new { x.TemplateId, x.Version });
            e.HasIndex(x => new { x.TemplateId, x.Version }).IsUnique();
            e.Property(x => x.Name).IsRequired();
            e.Property(x => x.CreatedAt).HasDefaultValueSql("now()");
            e.Property(x => x.UpdatedAt).HasDefaultValueSql("now()");
        });

        // ReportTemplateSections
        b.Entity<Entities.ReportTemplateSection>(e => {
            e.ToTable("report_template_sections");
            e.HasKey(x => x.TemplateSectionId);
            e.HasIndex(x => new { x.TemplateId, x.TemplateVersion });
            e.Property(x => x.SectionType).IsRequired();
            e.Property(x => x.Header).IsRequired();
            e.HasOne(x => x.Template)
                .WithMany(x => x.Sections)
                .HasForeignKey(x => new { x.TemplateId, x.TemplateVersion })
                .OnDelete(DeleteBehavior.Cascade);
        });

        // ReportTemplateBlocks
        b.Entity<Entities.ReportTemplateBlock>(e => {
            e.ToTable("report_template_blocks");
            e.HasKey(x => x.TemplateBlockId);
            e.HasIndex(x => x.TemplateSectionId);
            e.Property(x => x.BlockType).IsRequired();
            e.Property(x => x.LayoutHints).HasColumnType("jsonb").HasDefaultValueSql("'{}'::jsonb");
            e.HasOne(x => x.TemplateSection)
                .WithMany(x => x.Blocks)
                .HasForeignKey(x => x.TemplateSectionId)
                .OnDelete(DeleteBehavior.Cascade);
        });

        // Reports
        b.Entity<Entities.Report>(e => {
            e.ToTable("reports");
            e.HasKey(x => x.ReportId);
            e.HasIndex(x => x.TemplateId);
            e.HasIndex(x => x.WorkspaceAnalysisId);
            e.HasIndex(x => x.ScenarioId);
            e.Property(x => x.Type).IsRequired();
            e.Property(x => x.Title).IsRequired();
            e.Property(x => x.Status).IsRequired();
            e.Property(x => x.Metadata).HasColumnType("jsonb").HasDefaultValueSql("'{}'::jsonb");
            e.Property(x => x.CreatedAt).HasDefaultValueSql("now()");
            e.Property(x => x.UpdatedAt).HasDefaultValueSql("now()");
            
            // Optional composite foreign key to ReportTemplate
            e.HasOne(x => x.Template)
                .WithMany()
                .HasForeignKey(x => new { x.TemplateId, x.TemplateVersion })
                .IsRequired(false)
                .OnDelete(DeleteBehavior.Restrict);
            
            // Optional foreign keys to WorkspaceAnalysis and Scenario
            e.HasOne(x => x.WorkspaceAnalysis)
                .WithMany()
                .HasForeignKey(x => x.WorkspaceAnalysisId)
                .OnDelete(DeleteBehavior.Cascade);
            
            e.HasOne(x => x.Scenario)
                .WithMany()
                .HasForeignKey(x => x.ScenarioId)
                .OnDelete(DeleteBehavior.Cascade);
            
            // Check constraint: exactly one of WorkspaceAnalysisId or ScenarioId must be set
            e.ToTable(t => t.HasCheckConstraint("ck_report_parent", 
                "(workspace_analysis_id IS NOT NULL AND scenario_id IS NULL) OR (workspace_analysis_id IS NULL AND scenario_id IS NOT NULL)"));
        });

        // ReportSections
        b.Entity<Entities.ReportSection>(e => {
            e.ToTable("report_sections");
            e.HasKey(x => x.ReportSectionId);
            e.HasIndex(x => x.ReportId);
            e.Property(x => x.SectionType).IsRequired();
            e.Property(x => x.Header).IsRequired();
            e.HasOne(x => x.Report)
                .WithMany(x => x.Sections)
                .HasForeignKey(x => x.ReportId)
                .OnDelete(DeleteBehavior.Cascade);
            
            e.HasOne(x => x.TemplateSection)
                .WithMany()
                .HasForeignKey(x => x.TemplateSectionId)
                .IsRequired(false)
                .OnDelete(DeleteBehavior.Restrict);
        });

        // ReportBlocks
        b.Entity<Entities.ReportBlock>(e => {
            e.ToTable("report_blocks");
            e.HasKey(x => x.ReportBlockId);
            e.HasIndex(x => x.ReportSectionId);
            e.Property(x => x.BlockType).IsRequired();
            e.Property(x => x.SourceRefs).HasColumnType("text[]").HasDefaultValueSql("'{}'::text[]");
            e.Property(x => x.Provenance).HasColumnType("jsonb").HasDefaultValueSql("'{}'::jsonb");
            e.Property(x => x.LayoutHints).HasColumnType("jsonb").HasDefaultValueSql("'{}'::jsonb");
            e.HasOne(x => x.ReportSection)
                .WithMany(x => x.Blocks)
                .HasForeignKey(x => x.ReportSectionId)
                .OnDelete(DeleteBehavior.Cascade);
            
            e.HasOne(x => x.TemplateBlock)
                .WithMany()
                .HasForeignKey(x => x.TemplateBlockId)
                .IsRequired(false)
                .OnDelete(DeleteBehavior.Restrict);
        });

        // ReportBlockRichTexts
        b.Entity<Entities.ReportBlockRichText>(e => {
            e.ToTable("report_block_rich_texts");
            e.HasKey(x => x.ReportBlockId);
            e.Property(x => x.Content).IsRequired();
            e.HasOne(x => x.ReportBlock)
                .WithOne()
                .HasForeignKey<Entities.ReportBlockRichText>(x => x.ReportBlockId)
                .OnDelete(DeleteBehavior.Cascade);
        });

        // ReportBlockSingleMetrics
        b.Entity<Entities.ReportBlockSingleMetric>(e => {
            e.ToTable("report_block_single_metrics");
            e.HasKey(x => x.ReportBlockId);
            e.Property(x => x.Label).IsRequired();
            e.Property(x => x.Value).IsRequired();
            e.HasOne(x => x.ReportBlock)
                .WithOne()
                .HasForeignKey<Entities.ReportBlockSingleMetric>(x => x.ReportBlockId)
                .OnDelete(DeleteBehavior.Cascade);
        });

        // ReportBlockMultiMetrics
        b.Entity<Entities.ReportBlockMultiMetric>(e => {
            e.ToTable("report_block_multi_metrics");
            e.HasKey(x => x.ReportBlockId);
            e.Property(x => x.Metrics).HasColumnType("jsonb").HasDefaultValueSql("'[]'::jsonb");
            e.HasOne(x => x.ReportBlock)
                .WithOne()
                .HasForeignKey<Entities.ReportBlockMultiMetric>(x => x.ReportBlockId)
                .OnDelete(DeleteBehavior.Cascade);
        });

        // ReportBlockInsightCards
        b.Entity<Entities.ReportBlockInsightCard>(e => {
            e.ToTable("report_block_insight_cards");
            e.HasKey(x => x.ReportBlockId);
            e.Property(x => x.Title).IsRequired();
            e.Property(x => x.Body).IsRequired();
            e.HasOne(x => x.ReportBlock)
                .WithOne()
                .HasForeignKey<Entities.ReportBlockInsightCard>(x => x.ReportBlockId)
                .OnDelete(DeleteBehavior.Cascade);
        });

        // Sources
        b.Entity<Entities.Source>(e => {
            e.ToTable("sources");
            e.HasKey(x => x.SourceId);
            e.HasIndex(x => x.ReportId);
            e.Property(x => x.SourceType).IsRequired();
            e.Property(x => x.Metadata).HasColumnType("jsonb").HasDefaultValueSql("'{}'::jsonb");
            e.Property(x => x.CreatedAt).HasDefaultValueSql("now()");
            e.HasOne(x => x.Report)
                .WithMany(x => x.Sources)
                .HasForeignKey(x => x.ReportId)
                .OnDelete(DeleteBehavior.Cascade);
        });
    }
}
