import TrackerPanel from './components/TrackerPanel'

function App() {
  // The title now lives in TitleBar, rendered by TrackerPanel — it sits in the
  // same bar as the tabs, and the tab state that bar needs lives down there.
  return <TrackerPanel />
}

export default App
