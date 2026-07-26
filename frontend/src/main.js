import './styles/global.css';
import App from './App.svelte'
import { initErrorMonitoring } from './lib/monitoring.js'

initErrorMonitoring();

const app = new App({
  target: document.getElementById('app'),
})

export default app
