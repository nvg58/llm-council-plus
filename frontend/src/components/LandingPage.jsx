import './LandingPage.css';

export default function LandingPage({ onSelectMode }) {
    return (
        <div className="landing-page">
            <div className="landing-header">
                <h1 className="landing-title">
                    LLM Council <span className="title-plus">Plus</span>
                </h1>
                <p className="landing-subtitle">Choose your experience</p>
            </div>

            <div className="landing-cards">
                <button className="landing-card council-card" onClick={() => onSelectMode('council')}>
                    <div className="card-icon">⚖️</div>
                    <div className="card-body">
                        <h2 className="card-title">LLM Council</h2>
                        <p className="card-desc">
                            Multiple AI models deliberate in parallel. Peer ranking reveals the strongest
                            arguments. A chairman synthesizes the final answer.
                        </p>
                        <ul className="card-features">
                            <li>3-stage deliberation</li>
                            <li>Anonymous peer ranking</li>
                            <li>Chairman synthesis</li>
                        </ul>
                    </div>
                    <div className="card-cta">Enter Council →</div>
                </button>

                <button className="landing-card advisors-card" onClick={() => onSelectMode('advisors')}>
                    <div className="card-icon">🧑‍💼</div>
                    <div className="card-body">
                        <h2 className="card-title">LLM Advisors</h2>
                        <p className="card-desc">
                            Named advisor personas debate your question across configurable rounds.
                            They vote on the strongest argument and deliver a structured verdict.
                        </p>
                        <ul className="card-features">
                            <li>Persona-driven debate</li>
                            <li>Configurable rounds</li>
                            <li>Structured verdict</li>
                        </ul>
                    </div>
                    <div className="card-cta">Start Advisory Session →</div>
                </button>
            </div>
        </div>
    );
}
