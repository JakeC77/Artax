import { Box, Chip, Divider, Typography } from '@mui/material'
import Button from '../common/Button'

export default function CanvasPanel({ onClear }: { onClear: () => void }) {
  const metrics = [
    { title: '$11.3M/year', subtitle: 'Total spend' },
    { title: '58% (Ozempic)', subtitle: 'Share of diabetes GLP-1' },
    { title: '$1.7M–$2.4M / yr (15–22%)', subtitle: 'Projected savings (conservative)' },
    { title: '1,246 (12-month rolling)', subtitle: 'Members impacted' },
    { title: '4–6 weeks', subtitle: 'Time to implement (policy + member comms)' },
  ]

  return (
    <Box sx={{ }}>
      <Box
        sx={{
          border: '1px solid',
          borderColor: 'divider',
          borderRadius: 0.5,
          bgcolor: 'background.paper',
          p: 2,
        }}
      >
        <Box sx={{ display: 'flex', alignItems: 'center', gap: 1, mb: 1 }}>
          <Chip size="small" label="Critical" color="warning" variant="outlined" />
          <Typography variant="h6" sx={{ fontWeight: 700 }}>
            Ozempic drives 58% of annual spend (draft)
          </Typography>
          <Box sx={{ flex: 1 }} />
          <Button size="sm" variant="outline" onClick={onClear}>CLEAR CANVAS</Button>
          <Button size="sm" variant="primary">SAVE ARTIFACT</Button>
        </Box>

        <Typography variant="subtitle1" sx={{ fontWeight: 600, mb: 1 }}>
          Immediate opportunity for utilization management review
        </Typography>

        <Box
          sx={{
            display: 'grid',
            gridTemplateColumns: { xs: '1fr', sm: 'repeat(2, 1fr)', md: 'repeat(3, 1fr)' },
            mb: 2,
            gap: 1
          }}
        >
          {metrics.map((m, i) => (
            <Box
              key={i}
              sx={{
                p: 1.5,
                bgcolor: 'background.default',
                border: '1px solid',
                borderColor: 'divider',
                borderRadius: 0.5,
              }}
            >
              <Typography variant="h6" sx={{ fontWeight: 700 }}>
                {m.title}
              </Typography>
              <Typography variant="body2" color="text.secondary">
                {m.subtitle}
              </Typography>
            </Box>
          ))}
        </Box>

        <Box sx={{ mb: 2 }}>
          <Typography variant="subtitle1" sx={{ fontWeight: 700, mb: 0.5 }}>
            Why this matters?
          </Typography>
          <Typography variant="body2" color="text.secondary" sx={{ mb: 1 }}>
            Spend is concentrated in one brand despite clinically suitable alternatives. Utilization is rising faster than eligible population growth across plans, indicating policy and formulary misalignment.
          </Typography>

          <Typography variant="subtitle1" sx={{ fontWeight: 700, mb: 0.5 }}>
            Scope & Segments
          </Typography>
          <Box component="ul" sx={{ pl: 3, m: 0, color: 'text.secondary' }}>
            <li>Plans affected: Alpha PPO, Bravo HMO, Delta EPO, Horizon ASO</li>
            <li>High-intensity cohorts:</li>
            <Box component="ul" sx={{ pl: 3, m: 0 }}>
              <li>Starters without step therapy: 31% of Ozempic members</li>
              <li>Switching potential (coverage of alt. GLP-1s): 64% of members in PPO/EPO</li>
              <li>Prescribers with ≥10 Ozempic scripts/month: 14 prescribers</li>
            </Box>
          </Box>
        </Box>

        <Box sx={{ border: '1px solid', borderColor: 'divider', borderRadius: 0.5, p: 2, bgcolor: 'background.default' }}>
          <Typography variant="subtitle2" color="text.secondary" sx={{ fontWeight: 700 }}>
            Q1 2026 risks
          </Typography>
          <Divider sx={{ my: 1 }} />
          <Typography variant="body2" color="text.secondary" sx={{ mb: 1 }}>
            Analyze our current competitive position in the prescription transparency market and identify our top 3 strategic risks for Q1 2026
          </Typography>
          <Typography sx={{ fontWeight: 700, mb: 0.5 }}>Top 3 Strategic Risks</Typography>
          <Box component="ol" sx={{ pl: 3, m: 0, color: 'text.secondary' }}>
            <li>
              Customer Retention & Expansion Risk (High)
              <Box component="ul" sx={{ pl: 3, m: 0 }}>
                <li>Decline in client renewals and product complaints on GLP-1 features</li>
                <li>Financial impact: $2.4M ARR at risk across renewals</li>
                <li>Actions: introduce account stabilization taskforce; GLP-1 stability messaging</li>
              </Box>
            </li>
            <li>
              Data Pipeline Reliability (Medium)
              <Box component="ul" sx={{ pl: 3, m: 0 }}>
                <li>Ingestion instability affecting SLA and insight freshness</li>
                <li>Actions: harden pipelines; add monitoring and autoscaling</li>
              </Box>
            </li>
          </Box>
        </Box>
 
{/* 
        <Box sx={{ mb: 1.5, display: 'flex', alignItems: 'center', gap: 1 }}>
          <Typography variant="h6" sx={{ fontWeight: 700 }}>Analysis</Typography>
          <Box sx={{ color: 'text.secondary', fontSize: 12 }}>(mocked)</Box>
          <Box sx={{ flex: 1 }} />
          <Typography variant="caption" color="text.secondary" sx={{ cursor: 'pointer' }}>
            See more
          </Typography>
        </Box>
        <Box sx={{ display: 'grid', gap: 1.5, gridTemplateColumns: { xs: '1fr', md: '1fr 1fr' } }}>
          {ANALYSIS_CARDS.map((a, i) => (
            <Box key={i} sx={{ p: 1.5, border: '1px solid', borderColor: 'divider', borderRadius: 1.5 }}>
              <Box sx={{ display: 'flex', alignItems: 'center', gap: 1, mb: 0.5 }}>
                <Chip size="small" label={a.status} color="warning" variant="outlined" />
                <Typography sx={{ fontWeight: 700 }}>{a.title}</Typography>
              </Box>
              <Typography variant="body2" color="text.secondary" sx={{ mb: 0.5 }}>
                {a.summary}
              </Typography>
              <Typography variant="body2" sx={{ fontWeight: 600 }}>
                {a.callout}
              </Typography>
            </Box>
          ))}
        </Box> */}

        {/* <Box sx={{ mt: 2, mb: 0.5, display: 'flex', alignItems: 'center', gap: 1 }}>
          <Typography variant="h6" sx={{ fontWeight: 700 }}>Scenarios</Typography>
          <Box sx={{ color: 'text.secondary', fontSize: 12 }}>(mocked)</Box>
        </Box>
        <Box sx={{ display: 'grid', gap: 1.5, gridTemplateColumns: { xs: '1fr', md: '1fr 1fr' } }}>
          {SCENARIOS.map((s, i) => (
            <Box key={i} sx={{ p: 1.5, border: '1px solid', borderColor: 'divider', borderRadius: 1.5 }}>
              <Typography sx={{ fontWeight: 700, mb: 0.5 }}>{s.title}</Typography>
              <Box sx={{ display: 'flex', flexWrap: 'wrap', gap: 0, mb: 0.5 }}>
                {s.chips.map((c) => (
                  <Chip key={c} label={c} size="small" variant="outlined" />
                ))}
              </Box>
              <Typography variant="body2" color="text.secondary">{s.desc}</Typography>
            </Box>
          ))}
        </Box> */}
      </Box>
    </Box>
  )
}

