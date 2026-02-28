import { Navigate, Route, Routes } from 'react-router-dom'
import AppLayout from './layout/AppLayout'
import Workspace from './pages/Workspace'
import Login from './pages/Login'
import Entities from './pages/Entities'
import Relations from './pages/Relations'
import Home from './pages/Home'
import Notification from './pages/Notification'
import Settings from './pages/Settings'
import Semantics from './pages/Semantics'
import Knowledge from './pages/Knowledge'
// Import ontology-related pages
import OntologyCreation from './pages/OntologyCreation'
import OntologyDataLoader from './pages/OntologyDataLoader'
import OntologiesList from './pages/OntologiesList'
import IntentsList from './pages/IntentsList'
import IntentCreateEdit from './pages/IntentCreateEdit'
import AgentRolesList from './pages/AgentRolesList'
import AgentRoleCreateEdit from './pages/AgentRoleCreateEdit'
import WorkspacesList from './pages/WorkspacesList'
import NewWorkspacePage from './pages/NewWorkspacePage'
import Reports from './pages/Reports'
import ReportBuilder from './pages/ReportBuilder'
import ReportPreview from './pages/ReportPreview'
import DevTestDataScoping from './pages/DevTestDataScoping'
import { WorkspaceProvider } from './contexts/WorkspaceContext'
import ProtectedRoute from './components/auth/ProtectedRoute'

function App() {
  return (
    <WorkspaceProvider>
      <Routes>
        <Route path="/login" element={<Login />} />
        <Route
          path="/"
          element={
            <ProtectedRoute>
              <AppLayout />
            </ProtectedRoute>
          }
        >
          <Route index element={<Home />} />
          <Route path="workspaces" element={<WorkspacesList />} />
          <Route path="workspaces/:workspaceId/new" element={<NewWorkspacePage />} />
          <Route path="workspaces/new" element={<NewWorkspacePage />} />
          <Route path="workspaces/:workspaceId/edit" element={<NewWorkspacePage />} />
          <Route path="workspace" element={<Workspace />} />
          <Route path="entities" element={<Entities />} />
          <Route path="relations" element={<Relations />} />
          <Route path="semantics" element={<Semantics />} />
          <Route path="knowledge" element={<Knowledge />} />
          <Route path="knowledge/ontologies" element={<OntologiesList />} />
          <Route path="knowledge/ontology/create" element={<OntologyCreation />} />
          <Route path="knowledge/ontology/:ontologyId" element={<OntologyCreation />} />
          <Route path="knowledge/data-loader" element={<OntologyDataLoader />} />
          <Route path="intents" element={<IntentsList />} />
          <Route path="intent/create" element={<IntentCreateEdit />} />
          <Route path="intent/:intentId" element={<IntentCreateEdit />} />
          <Route path="agent-roles" element={<AgentRolesList />} />
          <Route path="agent-role/create" element={<AgentRoleCreateEdit />} />
          <Route path="agent-role/:agentRoleId" element={<AgentRoleCreateEdit />} />
          <Route path="knowledge/data-loader/:attachmentId" element={<OntologyDataLoader />} />
          <Route path="reports" element={<Reports />} />
          <Route path="reports/:reportId" element={<ReportBuilder />} />
          <Route path="reports/:reportId/preview" element={<ReportPreview />} />
          <Route path="notification" element={<Notification />} />
          <Route path="settings" element={<Settings />} />
          {/* Dev/Test routes - only for development */}
          <Route path="dev/data-scoping" element={<DevTestDataScoping />} />
        </Route>
        <Route path="*" element={<Navigate to="/" replace />} />
      </Routes>
    </WorkspaceProvider>
  )
}

export default App
