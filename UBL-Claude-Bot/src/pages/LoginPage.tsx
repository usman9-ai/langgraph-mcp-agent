import { useState } from 'react';
import { useNavigate } from 'react-router-dom';
import { FaIdBadge, FaLock } from 'react-icons/fa';
import { ToastContainer, toast } from 'react-toastify';
import 'react-toastify/dist/ReactToastify.css';

import loginImage from '../assets/images/login-image.jpg';
import logo from '../assets/images/ubl-logo.png';
import { loginRequest } from '../services/authService';
import { useStore } from '../store/useStore';

const Login = () => {
  const [employeeId, setEmployeeId] = useState('');
  const [password, setPassword] = useState('');
  const [showPassword, setShowPassword] = useState(false);
  const [errors, setErrors] = useState<{ employeeId?: string; password?: string }>({});
  const [serverMessage, setServerMessage] = useState<{ type: 'success' | 'error'; text: string } | null>(null);
  const [isSubmitting, setIsSubmitting] = useState(false);
  const navigate = useNavigate();
  const { setAuth } = useStore();

  const validateField = (name: 'employeeId' | 'password', value: string) => {
    let error = '';
    switch (name) {
      case 'employeeId':
        if (!value) {
          error = 'Employee ID is required.';
        }
        break;
      case 'password':
        if (!value) {
          error = 'Password is required.';
        }
        break;
      default:
        break;
    }
    setErrors((prevErrors) => ({ ...prevErrors, [name]: error }));
    return !error;
  };

  const handleLogin = async (e: React.FormEvent<HTMLFormElement>) => {
    e.preventDefault();
    const isEmployeeIdValid = validateField('employeeId', employeeId);
    const isPasswordValid = validateField('password', password);

    if (!isEmployeeIdValid || !isPasswordValid) {
      return;
    }

    try {
      setIsSubmitting(true);
      setServerMessage(null);
      const response = await loginRequest(employeeId, password);
      const authPayload = {
        employeeId,
        name: `Employee ${employeeId}`,
      };

      // Show success feedback before auth state flips route to /home.
      setServerMessage({ type: 'success', text: 'Login Successful' });
      toast.success('Login Successful', {
        position: 'top-center',
        autoClose: 1500,
      });

      setTimeout(() => {
        setAuth(response.access_token, authPayload);
        navigate('/home');
      }, 1500);
    } catch (error) {
      const message = error instanceof Error ? error.message : 'Login failed. Please try again.';
      setServerMessage({ type: 'error', text: message });
      toast.error(message, {
        position: 'top-center',
        autoClose: 3000,
      });
    } finally {
      setIsSubmitting(false);
    }
  };

  return (
    <div className="relative min-h-screen w-full overflow-hidden bg-primary text-text-primary">
      <img
        src={loginImage}
        alt="UBL login background"
        className="absolute inset-0 h-full w-full object-cover"
      />
      <div className="absolute inset-0 bg-black/55 backdrop-blur-sm" />

      <div className="relative z-10 flex min-h-screen items-center justify-center px-4 py-12">
        <div className="w-full max-w-md rounded-3xl border border-border-light bg-secondary/95 p-8 shadow-2xl shadow-black/10 backdrop-blur">
          <div className="flex flex-col items-center text-center">
            <img src={logo} alt="UBL Logo" className="h-16 w-auto" />
            <h2 className="mt-6 text-2xl font-semibold text-text-primary">Welcome back</h2>
            <p className="mt-2 text-sm text-text-secondary">
              Sign in with your corporate credentials to continue.
            </p>
          </div>

          <form onSubmit={handleLogin} noValidate className="mt-8 space-y-5">
            <div>
              <label htmlFor="employeeId" className="mb-2 block text-sm font-medium text-text-secondary">
                Employee ID
              </label>
              <div className="relative">
                <FaIdBadge className="absolute left-4 top-1/2 -translate-y-1/2 text-text-secondary" />
                <input
                  id="employeeId"
                  type="text"
                  className={`w-full rounded-2xl border bg-primary/40 py-3 pl-12 pr-4 text-sm text-text-primary shadow-sm outline-none transition-all focus:bg-primary/50 focus:shadow-md focus:ring-2 ${errors.employeeId
                      ? 'border-red-500 ring-red-100'
                      : 'border-border ring-accent/20 focus:border-accent'
                    }`}
                  placeholder="Enter your employee ID"
                  value={employeeId}
                  onChange={(e) => {
                    setEmployeeId(e.target.value);
                    if (errors.employeeId) validateField('employeeId', e.target.value);
                  }}
                  onBlur={() => validateField('employeeId', employeeId)}
                  required
                />
              </div>
              {errors.employeeId && (
                <p className="mt-2 text-sm font-medium text-red-500">{errors.employeeId}</p>
              )}
            </div>

            <div>
              <label htmlFor="password" className="mb-2 block text-sm font-medium text-text-secondary">
                Password
              </label>
              <div className="relative">
                <FaLock className="absolute left-4 top-1/2 -translate-y-1/2 text-text-secondary" />
                <input
                  id="password"
                  type={showPassword ? 'text' : 'password'}
                  className={`w-full rounded-2xl border bg-primary/40 py-3 pl-12 pr-20 text-sm text-text-primary shadow-sm outline-none transition-all focus:bg-primary/50 focus:shadow-md focus:ring-2 ${errors.password
                      ? 'border-red-500 ring-red-100'
                      : 'border-border ring-accent/20 focus:border-accent'
                    }`}
                  placeholder="Enter your password"
                  value={password}
                  onChange={(e) => {
                    setPassword(e.target.value);
                    if (errors.password) validateField('password', e.target.value);
                  }}
                  onBlur={() => validateField('password', password)}
                  required
                />
                <button
                  type="button"
                  onClick={() => setShowPassword((prev) => !prev)}
                  className="absolute right-3 top-1/2 -translate-y-1/2 rounded-md px-2 py-1 text-xs font-semibold text-accent hover:bg-primary/40"
                  aria-label={showPassword ? 'Hide password' : 'Show password'}
                >
                  {showPassword ? 'Hide' : 'Show'}
                </button>
              </div>
              {errors.password && (
                <p className="mt-2 text-sm font-medium text-red-500">{errors.password}</p>
              )}
            </div>

            <button
              type="submit"
              className="mt-2 w-full rounded-2xl bg-accent py-3 text-sm font-semibold text-white transition-all hover:bg-accent-hover hover:shadow-lg disabled:cursor-not-allowed disabled:opacity-60"
              disabled={!employeeId || !password || isSubmitting}
            >
              {isSubmitting ? 'Logging in...' : 'Log in'}
            </button>

            {serverMessage && (
              <div
                className={`rounded-2xl border px-4 py-3 text-sm font-semibold ${
                  serverMessage.type === 'success'
                    ? 'border-emerald-200 bg-emerald-50 text-emerald-900'
                    : 'border-rose-200 bg-rose-50 text-rose-900'
                }`}
                role="status"
                aria-live="polite"
              >
                {serverMessage.text}
              </div>
            )}
          </form>
        </div>
      </div>
      <ToastContainer
        position="top-center"
        hideProgressBar
        toastClassName={() =>
          // Make the message readable regardless of app theme variables.
          'relative flex items-center justify-between gap-3 overflow-hidden rounded-2xl border border-white/10 bg-slate-950 px-4 py-3 text-sm font-semibold text-white shadow-lg shadow-black/20'
        }
        className="flex-1 text-left"
      />
    </div>
  );
};

export default Login;
