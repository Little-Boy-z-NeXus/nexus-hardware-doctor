const components = ["ESP32", "INA219", "L298N", "DC motor"];

export function App() {
  return (
    <main>
      <header>
        <p className="eyebrow">NeXus Hardware Doctor</p>
        <h1>Hardware health: waiting for telemetry</h1>
        <p>The UI shell is ready for the Prevent, Manual Diagnose, and Auto Heal paths.</p>
      </header>

      <section aria-labelledby="rig-title">
        <h2 id="rig-title">MVP rig</h2>
        <ul>
          {components.map((component) => (
            <li key={component}>{component}</li>
          ))}
        </ul>
      </section>
    </main>
  );
}
