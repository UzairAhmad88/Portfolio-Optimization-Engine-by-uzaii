import React, { useState } from 'react';
import { useAuth } from '../../context/AuthContext';

export const AuthPage: React.FC = () => {
  const { login, register, authError, clearError } = useAuth();
  const [mode, setMode] = useState<'login' | 'register'>('login');

  const [email, setEmail] = useState('');
  const [password, setPassword] = useState('');
  const [fullName, setFullName] = useState('');
  const [isSubmitting, setIsSubmitting] = useState(false);
  const [localValidation, setLocalValidation] = useState<string | null>(null);

  const handleSubmit = async (e: React.FormEvent) => {
    e.preventDefault();
    setLocalValidation(null);
    clearError();

    if (!email.trim() || !password) {
      setLocalValidation('Please provide both email address and password.');
      return;
    }

    if (mode === 'register') {
      if (password.length < 8) {
        setLocalValidation('Password must be at least 8 characters long.');
        return;
      }
      if (!/[A-Z]/.test(password) || !/[a-z]/.test(password) || !/[0-9]/.test(password)) {
        setLocalValidation('Password must include uppercase, lowercase, and numeric characters.');
        return;
      }
    }

    setIsSubmitting(true);
    try {
      if (mode === 'login') {
        await login({ email: email.trim(), password });
      } else {
        await register({
          email: email.trim(),
          password,
          full_name: fullName.trim() || undefined,
          role: 'researcher',
        });
      }
    } catch {
      // Error handled in AuthContext
    } finally {
      setIsSubmitting(false);
    }
  };

  const toggleMode = (newMode: 'login' | 'register') => {
    setMode(newMode);
    clearError();
    setLocalValidation(null);
  };

  return (
    <div className="auth-container">
      <div className="auth-card">
        {/* Brand Banner */}
        <div className="auth-brand">
          <div className="auth-logo">Q</div>
          <div>
            <h1 className="auth-title">Quant Portfolio Engine</h1>
            <p className="auth-subtitle">Institutional Research & Risk Analytics Platform</p>
          </div>
        </div>

        {/* Mode Switcher */}
        <div className="auth-tabs" role="tablist">
          <button
            type="button"
            role="tab"
            aria-selected={mode === 'login'}
            className={`auth-tab ${mode === 'login' ? 'active' : ''}`}
            onClick={() => toggleMode('login')}
            id="tab-login"
          >
            Sign In
          </button>
          <button
            type="button"
            role="tab"
            aria-selected={mode === 'register'}
            className={`auth-tab ${mode === 'register' ? 'active' : ''}`}
            onClick={() => toggleMode('register')}
            id="tab-register"
          >
            Create Account
          </button>
        </div>

        {/* Error Banners */}
        {(authError || localValidation) && (
          <div className="auth-alert error" role="alert">
            <span className="auth-alert-icon">⚠️</span>
            <span>{localValidation || authError}</span>
          </div>
        )}

        {/* Form */}
        <form onSubmit={handleSubmit} className="auth-form" noValidate>
          {mode === 'register' && (
            <div className="form-group">
              <label htmlFor="auth-fullname">Full Name / Display Name</label>
              <input
                id="auth-fullname"
                type="text"
                placeholder="Dr. Alexander Vance"
                value={fullName}
                onChange={(e) => setFullName(e.target.value)}
                disabled={isSubmitting}
                className="auth-input"
              />
            </div>
          )}

          <div className="form-group">
            <label htmlFor="auth-email">Corporate Email Address</label>
            <input
              id="auth-email"
              type="email"
              required
              autoComplete="email"
              placeholder="researcher@firm.com"
              value={email}
              onChange={(e) => setEmail(e.target.value)}
              disabled={isSubmitting}
              className="auth-input"
            />
          </div>

          <div className="form-group">
            <label htmlFor="auth-password">Password</label>
            <input
              id="auth-password"
              type="password"
              required
              autoComplete={mode === 'login' ? 'current-password' : 'new-password'}
              placeholder="••••••••••••"
              value={password}
              onChange={(e) => setPassword(e.target.value)}
              disabled={isSubmitting}
              className="auth-input"
            />
            {mode === 'register' && (
              <span className="auth-hint">
                Minimum 8 characters with uppercase, lowercase, and numeric digits.
              </span>
            )}
          </div>

          <button
            type="submit"
            disabled={isSubmitting}
            className="auth-submit-btn"
            id="auth-submit-button"
          >
            {isSubmitting ? (
              <span className="auth-loading-text">
                <span className="spinner-sm"></span> Authenticating...
              </span>
            ) : mode === 'login' ? (
              'Enter Research Workspace'
            ) : (
              'Register Institutional Account'
            )}
          </button>
        </form>

        {/* Security Notice */}
        <div className="auth-footer">
          <p className="auth-security-notice">
            🔒 <strong>Secure Access Control:</strong> Server-enforced JWT access tokens with
            HttpOnly session protection and tenant-isolated portfolio data.
          </p>
        </div>
      </div>
    </div>
  );
};
