import React from "react";

/** Keeps a throwing chart/view from blanking the whole app mid-demo. */
export default class ErrorBoundary extends React.Component {
  constructor(props) {
    super(props);
    this.state = { error: null };
  }

  static getDerivedStateFromError(error) {
    return { error };
  }

  render() {
    if (this.state.error) {
      return (
        <div className="error" role="alert">
          <b>Something broke in this view:</b> {String(this.state.error.message || this.state.error)}
          <div style={{ marginTop: 8 }}>
            <button className="primary" onClick={() => this.setState({ error: null })}>
              Retry
            </button>
          </div>
        </div>
      );
    }
    return this.props.children;
  }
}
