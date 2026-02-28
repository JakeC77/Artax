"""
main.py - AI Workflow Manager
Entry point for the application
"""

from .cli import CLI, Menu, MenuItem
import os
import json
from pathlib import Path


# ============================================================================
# Hiring Manager
# ============================================================================
class HiringManager:
    def __init__(self):
        self.prompt = """"""
        self.invoke = ""
        self

# ============================================================================
# DATA MANAGEMENT (Simple file-based for now)
# ============================================================================

class DataManager:
    """Handle saving/loading projects and workflows"""
    
    def __init__(self):
        self.data_dir = Path("data")
        self.projects_dir = self.data_dir / "projects"
        self._ensure_dirs()
    
    def _ensure_dirs(self):
        """Create data directories if they don't exist"""
        self.projects_dir.mkdir(parents=True, exist_ok=True)
    
    def get_projects(self):
        """Get list of all projects"""
        if not self.projects_dir.exists():
            return []
        
        projects = []
        for project_dir in self.projects_dir.iterdir():
            if project_dir.is_dir():
                info_file = project_dir / "info.json"
                if info_file.exists():
                    with open(info_file, 'r') as f:
                        projects.append(json.load(f))
        return projects
    
    def create_project(self, name, context):
        """Create a new project.

        Args:
            name: Project name
            context: Project context/description

        Returns:
            Project info dict with id, name, and context

        Raises:
            ValueError: If a project with the same derived ID already exists.
                       The project ID is derived by lowercasing the name and
                       replacing spaces with underscores.
        """
        project_id = name.lower().replace(" ", "_")
        project_dir = self.projects_dir / project_id

        # Check for existing project to prevent accidental overwrite
        if project_dir.exists() or (project_dir / "info.json").exists():
            raise ValueError(
                f"Project with ID '{project_id}' already exists. "
                f"Please choose a different name or delete the existing project first."
            )

        # Create project directory
        project_dir.mkdir(exist_ok=False)

        # Create workflows directory
        (project_dir / "workflows").mkdir(exist_ok=False)

        # Save project info
        info = {
            "id": project_id,
            "name": name,
            "context": context
        }
        with open(project_dir / "info.json", 'w') as f:
            json.dump(info, f, indent=2)

        return info
    
    def get_workflows(self, project_id):
        """Get all workflows for a project"""
        workflows_dir = self.projects_dir / project_id / "workflows"
        if not workflows_dir.exists():
            return []
        
        workflows = []
        for workflow_file in workflows_dir.glob("*.json"):
            with open(workflow_file, 'r') as f:
                workflows.append(json.load(f))
        return workflows
    
    def create_workflow(self, project_id, name, intent):
        """Create a new workflow"""
        workflow_id = name.lower().replace(" ", "_")
        workflow_file = self.projects_dir / project_id / "workflows" / f"{workflow_id}.json"
        
        workflow = {
            "id": workflow_id,
            "name": name,
            "intent": intent,
            "agents": []  # For future use
        }
        
        with open(workflow_file, 'w') as f:
            json.dump(workflow, f, indent=2)
        
        return workflow


# ============================================================================
# APPLICATION
# ============================================================================

class WorkflowApp:
    """Main application logic"""
    
    def __init__(self):
        self.cli = CLI()
        self.data = DataManager()
        self.current_project = None
    
    # ========================================================================
    # PROJECT MANAGEMENT
    # ========================================================================
    
    def select_project(self):
        """Main project selection screen"""
        while True:
            self.cli.clear()
            self.cli.header("AI Workflow Manager")
            
            projects = self.data.get_projects()
            
            if projects:
                self.cli.section("Your Projects")
                for i, project in enumerate(projects, 1):
                    print(f"  {i}. {project['name']}")
                    if project.get('context'):
                        print(f"     {self.cli.Colors.DIM}{project['context'][:60]}...{self.cli.Colors.RESET}")
                print()
            
            print(f"  [n] Create New Project")
            print(f"  [q] Quit")
            
            choice = self.cli.input_text("\nSelect a project or create new", required=True)
            
            if not choice:
                continue
            
            choice = choice.lower()
            
            if choice == 'q':
                if self.cli.exit_handler():
                    return None
                continue
            
            elif choice == 'n':
                project = self.create_project()
                if project:
                    self.current_project = project
                    return project
            
            else:
                # Try to parse as number
                try:
                    idx = int(choice) - 1
                    if 0 <= idx < len(projects):
                        self.current_project = projects[idx]
                        return projects[idx]
                    else:
                        self.cli.error(f"Please enter a number between 1 and {len(projects)}")
                        self.cli.pause()
                except ValueError:
                    self.cli.error("Invalid selection. Enter a number or 'n' for new project")
                    self.cli.pause()
    
    def create_project(self):
        """Create a new project"""
        self.cli.clear()
        self.cli.header("Create New Project")
        
        # Get project name
        name = self.cli.input_text("Project name", required=True)
        if not name:
            return None
        
        # Get context
        print(f"\n{self.cli.Colors.CYAN}Project Context{self.cli.Colors.RESET}")
        print("Describe what this project is for, its goals, or any relevant info:")
        context = self.cli.input_text("Context (optional)", required=False)

        # Create project
        try:
            with self.cli.loading_spinner("Creating project"):
                project = self.data.create_project(name, context or "")

            self.cli.success(f"Project '{name}' created!")
            self.cli.pause()

            return project
        except ValueError as e:
            self.cli.error(str(e))
            self.cli.pause()
            return None
    
    # ========================================================================
    # PROJECT MENU
    # ========================================================================
    
    def show_project_menu(self):
        """Show menu for selected project"""
        project_menu = Menu(
            title=f"Project: {self.current_project['name']}",
            items=[
                MenuItem("1", "Build New Team (Talk to Theo)", self.create_workflow_flow),
                MenuItem("2", "Explore Teams", self.explore_agents),
            ],
            back_enabled=True
        )
        self.cli.navigate_to(project_menu)
    
    # ========================================================================
    # WORKFLOW MANAGEMENT
    # ========================================================================
    
    def create_workflow_flow(self):
        """
        Create a new workflow - two-stage process with Theo.

        Why: Two-stage approach separates intent discovery from team building.
        Theo operates in different modes with dynamically injected prompts.

        Workflow:
        1. Theo (Intent Mode) - discover and clarify intent
        2. Theo (Team Mode) - build team from intent
        3. Save both intent and team bundle
        """
        import asyncio
        from .intent_builder import IntentBuilder
        from .team_builder import TeamBuilder
        import json

        self.cli.clear()
        self.cli.header("Create New Team")

        print(f"\n{self.cli.Colors.CYAN}Let's build your team!{self.cli.Colors.RESET}")
        print("This is a two-stage process:")
        print("  1. Theo (Intent Mode) - clarify what you want")
        print("  2. Theo (Team Building Mode) - build the right team")
        print()

        # Optional: Get initial context
        print(f"{self.cli.Colors.DIM}(Optional) Give us a quick summary to get started:{self.cli.Colors.RESET}")
        initial_context = input("> ").strip()

        # ====================================================================
        # STAGE 1: THEO - INTENT DISCOVERY
        # ====================================================================
        try:
            intent_builder = IntentBuilder()

            # Run the async conversation with Theo
            intent_package = asyncio.run(
                intent_builder.start_conversation(
                    initial_context if initial_context else None
                )
            )

            if intent_package is None:
                # User quit early during intent discovery
                self.cli.warning("Team creation cancelled.")
                self.cli.pause()
                return

            # Show intent summary
            self.cli.clear()
            self.cli.success(f"Intent package complete!")
            print(f"\n{self.cli.Colors.GREEN}✓{self.cli.Colors.RESET} Title: {intent_package.title}")
            print(f"{self.cli.Colors.GREEN}✓{self.cli.Colors.RESET} Version: {intent_package.current_version}")
            print(f"{self.cli.Colors.GREEN}✓{self.cli.Colors.RESET} Iterations: {len(intent_package.iteration_history)}")
            print(f"\n{self.cli.Colors.CYAN}Summary:{self.cli.Colors.RESET}")
            print(f"{intent_package.summary}")
            print()

            # Confirm before moving to team building
            print(f"{self.cli.Colors.CYAN}Ready to move to team building?{self.cli.Colors.RESET}")
            print("Press Enter to continue, or 'q' to stop here...")

            confirm = input("> ").strip().lower()
            if confirm == 'q':
                self.cli.warning("Stopped after intent discovery. Team not built.")
                self.cli.pause()
                return

            # ====================================================================
            # STAGE 2: THEO (TEAM MODE) - TEAM BUILDING
            # ====================================================================
            print(f"\n{self.cli.Colors.CYAN}Starting team building with Theo...{self.cli.Colors.RESET}\n")

            team_builder = TeamBuilder()

            # Run the async conversation with Theo (team mode)
            team_bundle = asyncio.run(
                team_builder.start_conversation(intent_package)
            )

            if team_bundle is None:
                # User quit early during team building
                self.cli.warning("Team building cancelled.")
                self.cli.pause()
                return

            # ====================================================================
            # SAVE WORKFLOW WITH TEAM
            # ====================================================================
            workflow_name = intent_package.title

            # Save both intent package and team bundle reference
            # Why: Workflow now includes both intent AND the team that fulfills it
            conductor_display = f"{team_bundle.team_definition.conductor.identity.name} - {team_bundle.team_definition.conductor.identity.role}"
            specialist_displays = [s.identity.name for s in team_bundle.team_definition.specialists]

            workflow_data = {
                "intent_package": intent_package.to_handoff_dict(),
                "team_bundle": {
                    "team_name": team_bundle.team_name,
                    "location": f"teams/{team_bundle.team_name}",
                    "created_at": team_bundle.created_at.isoformat(),
                    "conductor": conductor_display,
                    "specialists": specialist_displays
                },
                "raw_text_summary": f"{intent_package.title}\n\n{intent_package.summary}"
            }

            with self.cli.loading_spinner("Saving workflow"):
                workflow = self.data.create_workflow(
                    self.current_project['id'],
                    workflow_name,
                    json.dumps(workflow_data, indent=2)
                )

            # ====================================================================
            # SUCCESS SUMMARY
            # ====================================================================
            self.cli.clear()
            self.cli.success(f"Team created successfully!")

            print(f"\n{self.cli.Colors.CYAN}Intent:{self.cli.Colors.RESET}")
            print(f"  Title: {intent_package.title}")
            print(f"  Summary: {intent_package.summary}")

            print(f"\n{self.cli.Colors.CYAN}Team:{self.cli.Colors.RESET}")
            print(f"  Name: {team_bundle.team_name}")
            print(f"  Conductor: {conductor_display}")
            if team_bundle.team_definition.specialists:
                print(f"  Specialists:")
                for spec in team_bundle.team_definition.specialists:
                    print(f"    - {spec.identity.name} ({spec.identity.focus})")
            else:
                print(f"  Specialists: None (Conductor works solo)")

            print(f"\n{self.cli.Colors.CYAN}Files:{self.cli.Colors.RESET}")
            print(f"  Team bundle: teams/{team_bundle.team_name}/")
            print(f"  Workflow: data/projects/{self.current_project['id']}/workflows/")

            print(f"\n{self.cli.Colors.GREEN}Your team is ready to deploy!{self.cli.Colors.RESET}")

            self.cli.pause()

        except Exception as e:
            self.cli.error(f"Error during team creation: {e}")
            import traceback
            traceback.print_exc()
            self.cli.pause()
    
    def manage_workflows(self):
        """Manage existing workflows"""
        self.cli.clear()
        self.cli.header("Manage Workflows")
        
        workflows = self.data.get_workflows(self.current_project['id'])
        
        if not workflows:
            self.cli.warning("No workflows yet. Create one first!")
            self.cli.pause()
            return
        
        # Show workflows in table
        rows = [[w['name'], w['intent'][:50] + "..."] for w in workflows]
        self.cli.table(["Workflow", "Intent"], rows)
        
        self.cli.info("Workflow management coming soon...")
        self.cli.pause()
    
    def explore_agents(self):
        """Explore teams for current project"""
        while True:
            self.cli.clear()
            self.cli.header(f"Explore Teams - {self.current_project['name']}")

            # Get workflows (which contain team references)
            workflows = self.data.get_workflows(self.current_project['id'])

            if not workflows:
                self.cli.warning("No teams yet. Build one first!")
                self.cli.pause()
                return

            # Display teams
            print(f"\n{self.cli.Colors.CYAN}Teams in this project:{self.cli.Colors.RESET}\n")
            for i, workflow in enumerate(workflows, 1):
                # Parse workflow intent to get team info
                try:
                    workflow_data = json.loads(workflow['intent'])
                    team_bundle = workflow_data.get('team_bundle', {})
                    intent_package = workflow_data.get('intent_package', {})

                    print(f"  {i}. {workflow['name']}")
                    if intent_package.get('summary'):
                        print(f"     {self.cli.Colors.DIM}{intent_package['summary'][:80]}...{self.cli.Colors.RESET}")
                    print(f"     {self.cli.Colors.DIM}Team: {team_bundle.get('conductor', 'Unknown')}{self.cli.Colors.RESET}")
                    print()
                except (json.JSONDecodeError, KeyError):
                    print(f"  {i}. {workflow['name']}")
                    print(f"     {self.cli.Colors.DIM}(Legacy workflow - limited info){self.cli.Colors.RESET}")
                    print()

            print(f"  [b] Back to project menu")

            choice = self.cli.input_text("\nSelect a team to explore", required=False)

            if not choice or choice.lower() == 'b':
                return

            # Try to parse as number
            try:
                idx = int(choice) - 1
                if 0 <= idx < len(workflows):
                    self.explore_team_detail(workflows[idx])
                else:
                    self.cli.error(f"Please enter a number between 1 and {len(workflows)}")
                    self.cli.pause()
            except ValueError:
                self.cli.error("Invalid selection. Enter a number or 'b' to go back")
                self.cli.pause()

    def explore_team_detail(self, workflow):
        """Show detailed view of a team"""
        while True:
            self.cli.clear()
            self.cli.header(f"Team: {workflow['name']}")

            # Parse workflow data
            try:
                workflow_data = json.loads(workflow['intent'])
                team_bundle = workflow_data.get('team_bundle', {})
                intent_package = workflow_data.get('intent_package', {})

                # Load team definition and intent from team directory
                team_location = team_bundle.get('location', '')
                if team_location:
                    team_dir = Path(team_location)

                    # Load intent package
                    intent_path = team_dir / "intent_package.json"
                    theo_def_path = team_dir / "theo_definition.json"

                    intent_data = None
                    theo_data = None

                    if intent_path.exists():
                        with open(intent_path, 'r') as f:
                            intent_data = json.load(f)

                    if theo_def_path.exists():
                        with open(theo_def_path, 'r') as f:
                            theo_data = json.load(f)

                    # Show menu
                    print(f"\n{self.cli.Colors.CYAN}What would you like to explore?{self.cli.Colors.RESET}\n")
                    print("  1. View Intent One-Pager")
                    print("  2. View Team Composition & Report")
                    print("  3. Explore Agents (Conductor & Specialists)")
                    print()
                    print("  [b] Back to team list")

                    choice = self.cli.input_text("\nSelect an option", required=False)

                    if not choice or choice.lower() == 'b':
                        return

                    if choice == '1':
                        self.show_intent_detail(intent_data or intent_package, workflow['name'])
                    elif choice == '2':
                        self.show_team_report(theo_data, workflow['name'])
                    elif choice == '3':
                        self.explore_team_agents(theo_data, team_dir, workflow['name'])
                    else:
                        self.cli.error("Invalid choice")
                        self.cli.pause()
                else:
                    self.cli.error("Team location not found in workflow data")
                    self.cli.pause()
                    return

            except (json.JSONDecodeError, KeyError) as e:
                self.cli.error(f"Error loading team data: {e}")
                self.cli.pause()
                return

    def show_intent_detail(self, intent_data, team_name):
        """Show intent one-pager"""
        self.cli.clear()
        self.cli.header(f"Intent: {team_name}")

        print(f"\n{self.cli.Colors.CYAN}Title:{self.cli.Colors.RESET}")
        print(f"  {intent_data.get('title', 'N/A')}")

        print(f"\n{self.cli.Colors.CYAN}Summary:{self.cli.Colors.RESET}")
        print(f"  {intent_data.get('summary', 'N/A')}")

        mission = intent_data.get('mission', {})
        if mission:
            print(f"\n{self.cli.Colors.CYAN}Mission:{self.cli.Colors.RESET}")
            print(f"\n  Objective: {mission.get('objective', 'N/A')}")
            print(f"\n  Why: {mission.get('why', 'N/A')}")
            print(f"\n  Success Looks Like: {mission.get('success_looks_like', 'N/A')}")

        team_guidance = intent_data.get('team_guidance', {})
        if team_guidance:
            print(f"\n{self.cli.Colors.CYAN}Team Building Guidance:{self.cli.Colors.RESET}")
            print(f"  Complexity: {team_guidance.get('complexity_level', 'N/A')}")
            print(f"  Collaboration Pattern: {team_guidance.get('collaboration_pattern', 'N/A')}")

            expertise = team_guidance.get('expertise_needed', [])
            if expertise:
                print(f"  Expertise Needed: {', '.join(expertise)}")

        self.cli.pause()

    def show_team_report(self, theo_data, team_name):
        """Show team composition and design report"""
        self.cli.clear()
        self.cli.header(f"Team Report: {team_name}")

        if not theo_data or 'report' not in theo_data:
            self.cli.error("Team report not found")
            self.cli.pause()
            return

        report = theo_data['report']

        print(f"\n{self.cli.Colors.CYAN}Intent Summary:{self.cli.Colors.RESET}")
        print(f"  {report.get('intent_summary', 'N/A')}")

        print(f"\n{self.cli.Colors.CYAN}Team Overview:{self.cli.Colors.RESET}")
        print(f"  {report.get('team_overview', 'N/A')}")

        design_rationale = report.get('design_rationale', {})
        if design_rationale:
            print(f"\n{self.cli.Colors.CYAN}Design Rationale:{self.cli.Colors.RESET}")
            print(f"\n  Structure Choice: {design_rationale.get('structure_choice', 'N/A')}")
            print(f"\n  Conductor: {design_rationale.get('conductor', 'N/A')}")
            print(f"\n  Specialists: {design_rationale.get('specialists', 'N/A')}")
            print(f"\n  Tool Assignments: {design_rationale.get('tool_assignments', 'N/A')}")

        trade_offs = report.get('trade_offs_made', {})
        if trade_offs:
            print(f"\n{self.cli.Colors.CYAN}Trade-offs Made:{self.cli.Colors.RESET}")
            print(f"  Depth vs Breadth: {trade_offs.get('depth_vs_breadth', 'N/A')}")
            print(f"  Speed vs Thoroughness: {trade_offs.get('speed_vs_thoroughness', 'N/A')}")
            print(f"  Autonomy vs Control: {trade_offs.get('autonomy_vs_control', 'N/A')}")

        failure_modes = report.get('failure_modes_addressed', [])
        if failure_modes:
            print(f"\n{self.cli.Colors.CYAN}Failure Modes Addressed:{self.cli.Colors.RESET}")
            for mode in failure_modes:
                print(f"  • {mode}")

        human_in_loop = report.get('human_in_loop_points', [])
        if human_in_loop:
            print(f"\n{self.cli.Colors.CYAN}Human-in-Loop Points:{self.cli.Colors.RESET}")
            for point in human_in_loop:
                print(f"  • {point}")

        self.cli.pause()

    def explore_team_agents(self, theo_data, team_dir, team_name):
        """Explore individual agents in the team"""
        while True:
            self.cli.clear()
            self.cli.header(f"Agents: {team_name}")

            if not theo_data:
                self.cli.error("Team data not found")
                self.cli.pause()
                return

            conductor = theo_data.get('conductor', {})
            specialists = theo_data.get('specialists', [])

            print(f"\n{self.cli.Colors.CYAN}Agents in this team:{self.cli.Colors.RESET}\n")

            # Show conductor
            conductor_identity = conductor.get('identity', {})
            print(f"  1. {conductor_identity.get('name', 'Unknown')} - {conductor_identity.get('role', 'Conductor')}")
            print(f"     {self.cli.Colors.DIM}(Conductor){self.cli.Colors.RESET}")
            print()

            # Show specialists
            for i, spec in enumerate(specialists, 2):
                spec_identity = spec.get('identity', {})
                print(f"  {i}. {spec_identity.get('name', 'Unknown')}")
                print(f"     {self.cli.Colors.DIM}{spec_identity.get('focus', 'Specialist')}{self.cli.Colors.RESET}")
                print()

            print(f"  [b] Back to team menu")

            choice = self.cli.input_text("\nSelect an agent to view details", required=False)

            if not choice or choice.lower() == 'b':
                return

            # Try to parse as number
            try:
                idx = int(choice) - 1
                if idx == 0:
                    self.show_agent_detail(conductor, "Conductor", team_dir)
                elif 0 < idx <= len(specialists):
                    self.show_agent_detail(specialists[idx - 1], "Specialist", team_dir)
                else:
                    self.cli.error(f"Please enter a number between 1 and {len(specialists) + 1}")
                    self.cli.pause()
            except ValueError:
                self.cli.error("Invalid selection. Enter a number or 'b' to go back")
                self.cli.pause()

    def show_agent_detail(self, agent_data, agent_type, team_dir):
        """Show detailed view of an individual agent"""
        self.cli.clear()

        identity = agent_data.get('identity', {})
        name = identity.get('name', 'Unknown')
        role = identity.get('role', identity.get('focus', 'Unknown'))

        self.cli.header(f"{agent_type}: {name}")

        print(f"\n{self.cli.Colors.CYAN}Identity:{self.cli.Colors.RESET}")
        print(f"  Name: {name}")
        print(f"  Role: {role}")

        # Show persona (if conductor)
        persona = agent_data.get('persona', {})
        if persona:
            print(f"\n{self.cli.Colors.CYAN}Persona:{self.cli.Colors.RESET}")
            print(f"  Background: {persona.get('background', 'N/A')}")
            print(f"  Communication Style: {persona.get('communication_style', 'N/A')}")
            print(f"  Personality: {persona.get('personality', 'N/A')}")

        # Show service delivery
        service_delivery = agent_data.get('service_delivery', {})
        if service_delivery:
            print(f"\n{self.cli.Colors.CYAN}Service Delivery:{self.cli.Colors.RESET}")
            print(f"  Core Responsibility: {service_delivery.get('core_responsibility', 'N/A')}")

            deliverables = service_delivery.get('deliverables', [])
            if deliverables:
                print(f"\n  Deliverables:")
                for deliverable in deliverables[:5]:  # Show first 5
                    print(f"    • {deliverable}")

            capabilities = service_delivery.get('capabilities', [])
            if capabilities:
                print(f"\n  Capabilities:")
                for cap in capabilities[:5]:  # Show first 5
                    print(f"    • {cap}")

        # Show tools
        tools = agent_data.get('tools', {})
        if tools:
            available_tools = tools.get('available', [])
            if available_tools:
                print(f"\n{self.cli.Colors.CYAN}Tools:{self.cli.Colors.RESET}")
                print(f"  {', '.join(available_tools)}")

        # Show philosophy
        philosophy = agent_data.get('philosophy', {})
        if philosophy:
            print(f"\n{self.cli.Colors.CYAN}Philosophy:{self.cli.Colors.RESET}")
            print(f"  Problem Solving Approach:")
            print(f"    {philosophy.get('problem_solving_approach', 'N/A')[:200]}...")

            principles = philosophy.get('guiding_principles', [])
            if principles:
                print(f"\n  Guiding Principles:")
                for principle in principles[:3]:  # Show first 3
                    print(f"    • {principle}")

        # Note about full definition
        print(f"\n{self.cli.Colors.DIM}(Full agent definition available in {team_dir}/agents/){self.cli.Colors.RESET}")

        self.cli.pause()
    
    # ========================================================================
    # RUN APPLICATION
    # ========================================================================
    
    def run(self):
        """Main application loop"""
        # Step 1: Select or create project
        try:
            while self.cli.running:
                project = self.select_project()
                
                if not project:
                    # User quit during project selection
                    return

                if not self.cli.running:
                    break
                
                # Step 2: Show project menu
                self.show_project_menu()
        except KeyboardInterrupt:
            print()
            self.cli.exit_handler()


# ============================================================================
# ENTRY POINT
# ============================================================================

if __name__ == "__main__":
    app = WorkflowApp()
    app.run()