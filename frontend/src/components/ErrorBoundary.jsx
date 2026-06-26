import React from 'react'

// Catches render errors anywhere below it so one broken page can never blank
// the whole app. Shows a friendly fallback with a reload escape hatch.
export default class ErrorBoundary extends React.Component {
  constructor(props) {
    super(props)
    this.state = { error: null }
  }

  static getDerivedStateFromError(error) {
    return { error }
  }

  componentDidCatch(error, info) {
    // eslint-disable-next-line no-console
    console.error('UI error boundary caught:', error, info)
  }

  render() {
    if (this.state.error) {
      return (
        <div className="min-h-[60vh] flex items-center justify-center p-6">
          <div className="bg-white rounded-xl border border-red-100 p-8 max-w-lg text-center shadow-sm">
            <div className="text-3xl mb-3">⚠️</div>
            <h2 className="text-lg font-bold text-gray-800 mb-1">Something went wrong on this page</h2>
            <p className="text-sm text-gray-500 mb-4">
              The rest of the app is fine. You can go back to the dashboard or reload this page.
            </p>
            <p className="text-xs text-gray-400 font-mono mb-5 break-all">{String(this.state.error?.message || this.state.error)}</p>
            <div className="flex items-center justify-center gap-3">
              <button onClick={() => { this.setState({ error: null }); window.location.href = import.meta.env.BASE_URL + 'dashboard' }}
                className="btn-primary text-sm">Go to Dashboard</button>
              <button onClick={() => window.location.reload()}
                className="btn-ghost text-sm">Reload page</button>
            </div>
          </div>
        </div>
      )
    }
    return this.props.children
  }
}
