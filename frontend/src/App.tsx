import { Badge } from '@/components/ui/badge'
import { Card, CardContent, CardHeader, CardTitle } from '@/components/ui/card'
import sampleDiagnosis from '@/sample/sample_diagnosis.json'
import sampleRunJson from '@/sample/sample_run.json'
import type { Diagnosis, Run } from '@/types/contract'

// JSON imports widen string literals, so the run needs a cast; backend/tests/test_contract.py
// is the strict check for both samples.
const sampleRun = sampleRunJson as Run
const diagnosis: Diagnosis = sampleDiagnosis

function App() {
  return (
    <main className="mx-auto max-w-3xl p-6">
      <Card>
        <CardHeader>
          <CardTitle>Black Box</CardTitle>
        </CardHeader>
        <CardContent className="space-y-2 text-sm">
          <p>{sampleRun.request_text}</p>
          <p>
            {sampleRun.steps.length} steps · outcome{' '}
            <Badge variant={sampleRun.outcome === 'success' ? 'default' : 'destructive'}>{sampleRun.outcome}</Badge>{' '}
            · culprit step {diagnosis.culprit}
          </p>
        </CardContent>
      </Card>
    </main>
  )
}

export default App
