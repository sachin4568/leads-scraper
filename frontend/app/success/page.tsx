'use client';

import React, { useEffect, useState } from 'react';
import { api, CustomerAPI, CustomerHealthAPI, RetainerAPI, SuccessMetricsAPI, UpsellOpportunityAPI } from '../lib/api';

export default function CustomerSuccessPage() {
  const [metrics, setMetrics] = useState<SuccessMetricsAPI | null>(null);
  const [retainers, setRetainers] = useState<RetainerAPI[]>([]);
  const [healthMatrix, setHealthMatrix] = useState<CustomerHealthAPI[]>([]);
  const [upsells, setUpsells] = useState<UpsellOpportunityAPI[]>([]);
  const [customers, setCustomers] = useState<CustomerAPI[]>([]);
  const [activeTab, setActiveTab] = useState<'retainers' | 'health' | 'upsells'>('retainers');
  const [loading, setLoading] = useState<boolean>(true);
  const [healthFilter, setHealthFilter] = useState<string>('ALL');

  // Modal States
  const [isRetainerModalOpen, setIsRetainerModalOpen] = useState<boolean>(false);
  const [selectedCustomerId, setSelectedCustomerId] = useState<string>('');
  const [serviceType, setServiceType] = useState<string>('SEO_RETAINER');
  const [billingFreq, setBillingFreq] = useState<string>('MONTHLY');
  const [billingAmount, setBillingAmount] = useState<number>(15000);
  const [retainerNotes, setRetainerNotes] = useState<string>('');

  const loadData = async () => {
    try {
      setLoading(true);
      const [m, r, h, u, c] = await Promise.all([
        api.getSuccessMetrics(),
        api.getRetainers(),
        api.getCustomerHealthMatrix(),
        api.getUpsellOpportunities(),
        api.getCustomers({ page: 1, page_size: 100 }),
      ]);
      setMetrics(m);
      setRetainers(r);
      setHealthMatrix(h);
      setUpsells(u);
      setCustomers(c.customers);
      if (c.customers.length > 0 && !selectedCustomerId) {
        setSelectedCustomerId(c.customers[0].id);
      }
    } catch (err) {
      console.error('Failed to load customer success data:', err);
    } finally {
      setLoading(false);
    }
  };

  useEffect(() => {
    loadData();
  }, []);

  const handleCreateRetainer = async (e: React.FormEvent) => {
    e.preventDefault();
    if (!selectedCustomerId) return;
    try {
      await api.createCustomerRetainer(selectedCustomerId, {
        service_type: serviceType,
        billing_frequency: billingFreq,
        billing_amount: billingAmount,
        notes: retainerNotes,
        auto_renew: true,
      });
      setIsRetainerModalOpen(false);
      setRetainerNotes('');
      await loadData();
    } catch (err) {
      console.error('Failed to create retainer:', err);
    }
  };

  const handleRenewRetainer = async (retainerId: string) => {
    try {
      await api.renewRetainer(retainerId);
      await loadData();
    } catch (err) {
      console.error('Failed to renew retainer:', err);
    }
  };

  const handleUpdateUpsellStatus = async (upsellId: string, status: string) => {
    try {
      await api.updateUpsellStatus(upsellId, status);
      await loadData();
    } catch (err) {
      console.error('Failed to update upsell status:', err);
    }
  };

  const getHealthBadge = (health: string) => {
    switch (health) {
      case 'HEALTHY':
        return <span className="px-2.5 py-1 text-xs font-semibold rounded-full bg-emerald-100 text-emerald-800 dark:bg-emerald-900/40 dark:text-emerald-300">🟢 HEALTHY</span>;
      case 'AT_RISK':
        return <span className="px-2.5 py-1 text-xs font-semibold rounded-full bg-amber-100 text-amber-800 dark:bg-amber-900/40 dark:text-amber-300">🟡 AT RISK</span>;
      case 'CRITICAL':
        return <span className="px-2.5 py-1 text-xs font-semibold rounded-full bg-rose-100 text-rose-800 dark:bg-rose-900/40 dark:text-rose-300">🔴 CRITICAL</span>;
      case 'DORMANT':
        return <span className="px-2.5 py-1 text-xs font-semibold rounded-full bg-slate-100 text-slate-800 dark:bg-slate-800 dark:text-slate-300">⚪ DORMANT</span>;
      default:
        return <span className="px-2.5 py-1 text-xs font-semibold rounded-full bg-blue-100 text-blue-800">{health}</span>;
    }
  };

  const filteredHealthMatrix = healthFilter === 'ALL'
    ? healthMatrix
    : healthMatrix.filter(h => h.health_score === healthFilter);

  return (
    <div className="p-8 max-w-7xl mx-auto space-y-8">
      {/* Header */}
      <div className="flex flex-col md:flex-row justify-between items-start md:items-center gap-4">
        <div>
          <h1 className="text-3xl font-bold text-slate-900 dark:text-white tracking-tight">
            Customer Success & Recurring Revenue
          </h1>
          <p className="text-sm text-slate-500 dark:text-slate-400 mt-1">
            Track client health, manage retainers & renewals, and unlock expansion MRR.
          </p>
        </div>
        <div className="flex items-center gap-3">
          <button
            onClick={() => setIsRetainerModalOpen(true)}
            className="px-4 py-2.5 bg-blue-600 hover:bg-blue-700 text-white text-sm font-medium rounded-lg shadow-sm transition-all flex items-center gap-2"
          >
            <span>+</span>
            <span>New Retainer Contract</span>
          </button>
        </div>
      </div>

      {/* KPI Cards */}
      {metrics && (
        <div className="grid grid-cols-1 sm:grid-cols-2 lg:grid-cols-6 gap-4">
          <div className="bg-white dark:bg-slate-900 p-5 rounded-xl border border-slate-200 dark:border-slate-800 shadow-sm">
            <span className="text-xs font-medium text-slate-500 dark:text-slate-400 uppercase tracking-wider">Monthly MRR</span>
            <div className="text-2xl font-bold text-emerald-600 dark:text-emerald-400 mt-2">
              ₹{metrics.total_mrr.toLocaleString()}
            </div>
            <div className="text-xs text-slate-400 mt-1">Active recurring monthly</div>
          </div>

          <div className="bg-white dark:bg-slate-900 p-5 rounded-xl border border-slate-200 dark:border-slate-800 shadow-sm">
            <span className="text-xs font-medium text-slate-500 dark:text-slate-400 uppercase tracking-wider">Annualized ARR</span>
            <div className="text-2xl font-bold text-blue-600 dark:text-blue-400 mt-2">
              ₹{metrics.total_arr.toLocaleString()}
            </div>
            <div className="text-xs text-slate-400 mt-1">12-month run rate</div>
          </div>

          <div className="bg-white dark:bg-slate-900 p-5 rounded-xl border border-slate-200 dark:border-slate-800 shadow-sm">
            <span className="text-xs font-medium text-slate-500 dark:text-slate-400 uppercase tracking-wider">Active Retainers</span>
            <div className="text-2xl font-bold text-slate-900 dark:text-white mt-2">
              {metrics.active_retainers_count}
            </div>
            <div className="text-xs text-slate-400 mt-1">Across {metrics.active_customers} customers</div>
          </div>

          <div className="bg-white dark:bg-slate-900 p-5 rounded-xl border border-slate-200 dark:border-slate-800 shadow-sm">
            <span className="text-xs font-medium text-slate-500 dark:text-slate-400 uppercase tracking-wider">Renewals Due (30D)</span>
            <div className="text-2xl font-bold text-amber-600 dark:text-amber-400 mt-2">
              {metrics.renewals_due_30d_count}
            </div>
            <div className="text-xs text-slate-400 mt-1">Upcoming renewal cycle</div>
          </div>

          <div className="bg-white dark:bg-slate-900 p-5 rounded-xl border border-slate-200 dark:border-slate-800 shadow-sm">
            <span className="text-xs font-medium text-slate-500 dark:text-slate-400 uppercase tracking-wider">At-Risk Clients</span>
            <div className="text-2xl font-bold text-rose-600 dark:text-rose-400 mt-2">
              {metrics.at_risk_customers + metrics.critical_customers}
            </div>
            <div className="text-xs text-slate-400 mt-1">{metrics.healthy_customers} Healthy</div>
          </div>

          <div className="bg-white dark:bg-slate-900 p-5 rounded-xl border border-slate-200 dark:border-slate-800 shadow-sm">
            <span className="text-xs font-medium text-slate-500 dark:text-slate-400 uppercase tracking-wider">Expansion Pipeline</span>
            <div className="text-2xl font-bold text-indigo-600 dark:text-indigo-400 mt-2">
              ₹{metrics.expansion_pipeline_value.toLocaleString()}
            </div>
            <div className="text-xs text-slate-400 mt-1">Identified Upsells</div>
          </div>
        </div>
      )}

      {/* Tabs */}
      <div className="border-b border-slate-200 dark:border-slate-800">
        <nav className="flex space-x-8">
          <button
            onClick={() => setActiveTab('retainers')}
            className={`py-4 px-1 border-b-2 font-medium text-sm transition-all ${
              activeTab === 'retainers'
                ? 'border-blue-600 text-blue-600 dark:text-blue-400'
                : 'border-transparent text-slate-500 hover:text-slate-700 dark:text-slate-400'
            }`}
          >
            Retainers & Subscriptions ({retainers.length})
          </button>
          <button
            onClick={() => setActiveTab('health')}
            className={`py-4 px-1 border-b-2 font-medium text-sm transition-all ${
              activeTab === 'health'
                ? 'border-blue-600 text-blue-600 dark:text-blue-400'
                : 'border-transparent text-slate-500 hover:text-slate-700 dark:text-slate-400'
            }`}
          >
            Customer Health Matrix ({healthMatrix.length})
          </button>
          <button
            onClick={() => setActiveTab('upsells')}
            className={`py-4 px-1 border-b-2 font-medium text-sm transition-all ${
              activeTab === 'upsells'
                ? 'border-blue-600 text-blue-600 dark:text-blue-400'
                : 'border-transparent text-slate-500 hover:text-slate-700 dark:text-slate-400'
            }`}
          >
            Expansion & Upsell Pipeline ({upsells.length})
          </button>
        </nav>
      </div>

      {/* Tab 1: Retainers */}
      {activeTab === 'retainers' && (
        <div className="bg-white dark:bg-slate-900 rounded-xl border border-slate-200 dark:border-slate-800 overflow-hidden shadow-sm">
          <div className="p-5 border-b border-slate-200 dark:border-slate-800 flex justify-between items-center">
            <h2 className="text-base font-semibold text-slate-900 dark:text-white">
              Recurring Retainer Contracts
            </h2>
            <span className="text-xs text-slate-400">Total: {retainers.length} active/expiring</span>
          </div>

          <div className="overflow-x-auto">
            <table className="w-full text-left text-sm text-slate-600 dark:text-slate-300">
              <thead className="bg-slate-50 dark:bg-slate-800/50 text-xs font-semibold text-slate-500 dark:text-slate-400 uppercase tracking-wider">
                <tr>
                  <th className="py-3.5 px-6">Customer</th>
                  <th className="py-3.5 px-6">Service</th>
                  <th className="py-3.5 px-6">Billing</th>
                  <th className="py-3.5 px-6">Amount</th>
                  <th className="py-3.5 px-6">MRR</th>
                  <th className="py-3.5 px-6">Renewal Date</th>
                  <th className="py-3.5 px-6">Status</th>
                  <th className="py-3.5 px-6 text-right">Action</th>
                </tr>
              </thead>
              <tbody className="divide-y divide-slate-100 dark:divide-slate-800">
                {retainers.length === 0 ? (
                  <tr>
                    <td colSpan={8} className="py-8 text-center text-slate-400">
                      No recurring retainers recorded yet. Create one with "+ New Retainer Contract".
                    </td>
                  </tr>
                ) : (
                  retainers.map((r) => (
                    <tr key={r.id} className="hover:bg-slate-50 dark:hover:bg-slate-800/30 transition-colors">
                      <td className="py-4 px-6 font-medium text-slate-900 dark:text-white">
                        {r.customer_name}
                      </td>
                      <td className="py-4 px-6">
                        <span className="px-2.5 py-1 text-xs font-semibold rounded-md bg-blue-50 text-blue-700 dark:bg-blue-900/30 dark:text-blue-300 border border-blue-100 dark:border-blue-800">
                          {r.service_type.replace('_', ' ')}
                        </span>
                      </td>
                      <td className="py-4 px-6 text-xs text-slate-500 font-medium">
                        {r.billing_frequency}
                      </td>
                      <td className="py-4 px-6 font-semibold text-slate-900 dark:text-white">
                        ₹{r.billing_amount.toLocaleString()}
                      </td>
                      <td className="py-4 px-6 font-semibold text-emerald-600 dark:text-emerald-400">
                        +₹{r.monthly_mrr.toLocaleString()}/mo
                      </td>
                      <td className="py-4 px-6 text-xs text-slate-500">
                        {new Date(r.renewal_date).toLocaleDateString()}
                      </td>
                      <td className="py-4 px-6">
                        <span className={`px-2 py-0.5 text-xs font-medium rounded-full ${
                          r.status === 'ACTIVE'
                            ? 'bg-emerald-100 text-emerald-800 dark:bg-emerald-900/40 dark:text-emerald-300'
                            : r.status === 'EXPIRING_SOON'
                            ? 'bg-amber-100 text-amber-800 dark:bg-amber-900/40 dark:text-amber-300'
                            : 'bg-slate-100 text-slate-700 dark:bg-slate-800 dark:text-slate-300'
                        }`}>
                          {r.status}
                        </span>
                      </td>
                      <td className="py-4 px-6 text-right">
                        <button
                          onClick={() => handleRenewRetainer(r.id)}
                          className="px-3 py-1.5 text-xs font-medium text-blue-600 hover:text-blue-700 dark:text-blue-400 hover:bg-blue-50 dark:hover:bg-blue-950/40 rounded-lg transition-colors border border-blue-200 dark:border-blue-800"
                        >
                          🔄 Renew
                        </button>
                      </td>
                    </tr>
                  ))
                )}
              </tbody>
            </table>
          </div>
        </div>
      )}

      {/* Tab 2: Health Matrix */}
      {activeTab === 'health' && (
        <div className="space-y-6">
          <div className="flex gap-2">
            {['ALL', 'HEALTHY', 'AT_RISK', 'CRITICAL', 'DORMANT'].map((filter) => (
              <button
                key={filter}
                onClick={() => setHealthFilter(filter)}
                className={`px-3 py-1.5 text-xs font-medium rounded-lg transition-all ${
                  healthFilter === filter
                    ? 'bg-blue-600 text-white shadow-sm'
                    : 'bg-white dark:bg-slate-900 text-slate-600 dark:text-slate-300 border border-slate-200 dark:border-slate-800 hover:bg-slate-50'
                }`}
              >
                {filter}
              </button>
            ))}
          </div>

          <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-3 gap-6">
            {filteredHealthMatrix.map((cust) => (
              <div
                key={cust.id}
                className="bg-white dark:bg-slate-900 rounded-xl border border-slate-200 dark:border-slate-800 p-6 shadow-sm flex flex-col justify-between space-y-4"
              >
                <div>
                  <div className="flex justify-between items-start">
                    <h3 className="text-lg font-bold text-slate-900 dark:text-white">
                      {cust.company_name}
                    </h3>
                    {getHealthBadge(cust.health_score)}
                  </div>
                  <p className="text-xs text-slate-500 dark:text-slate-400 mt-2">
                    {cust.health_reason || 'Customer in normal operating state.'}
                  </p>
                </div>

                <div className="grid grid-cols-2 gap-3 py-3 border-y border-slate-100 dark:border-slate-800 text-xs">
                  <div>
                    <span className="text-slate-400">Monthly MRR</span>
                    <p className="font-bold text-emerald-600 dark:text-emerald-400 mt-0.5">
                      ₹{cust.mrr.toLocaleString()}/mo
                    </p>
                  </div>
                  <div>
                    <span className="text-slate-400">Lifetime Value</span>
                    <p className="font-bold text-slate-900 dark:text-white mt-0.5">
                      ₹{cust.lifetime_value.toLocaleString()}
                    </p>
                  </div>
                  <div>
                    <span className="text-slate-400">Retainers</span>
                    <p className="font-medium text-slate-700 dark:text-slate-300 mt-0.5">
                      {cust.active_retainers_count} Active
                    </p>
                  </div>
                  <div>
                    <span className="text-slate-400">Next Renewal</span>
                    <p className="font-medium text-slate-700 dark:text-slate-300 mt-0.5">
                      {cust.next_renewal_date ? new Date(cust.next_renewal_date).toLocaleDateString() : 'None'}
                    </p>
                  </div>
                </div>

                <div className="flex justify-end">
                  <button
                    onClick={() => {
                      setSelectedCustomerId(cust.id);
                      setIsRetainerModalOpen(true);
                    }}
                    className="text-xs font-medium text-blue-600 dark:text-blue-400 hover:underline"
                  >
                    + Add Retainer Contract
                  </button>
                </div>
              </div>
            ))}
          </div>
        </div>
      )}

      {/* Tab 3: Upsells */}
      {activeTab === 'upsells' && (
        <div className="bg-white dark:bg-slate-900 rounded-xl border border-slate-200 dark:border-slate-800 overflow-hidden shadow-sm">
          <div className="p-5 border-b border-slate-200 dark:border-slate-800">
            <h2 className="text-base font-semibold text-slate-900 dark:text-white">
              Deterministic Expansion & Upsell Pipeline
            </h2>
            <p className="text-xs text-slate-500 dark:text-slate-400 mt-1">
              Rule-based upsell pitches generated from completed services and missing foundations.
            </p>
          </div>

          <div className="overflow-x-auto">
            <table className="w-full text-left text-sm text-slate-600 dark:text-slate-300">
              <thead className="bg-slate-50 dark:bg-slate-800/50 text-xs font-semibold text-slate-500 dark:text-slate-400 uppercase tracking-wider">
                <tr>
                  <th className="py-3.5 px-6">Customer</th>
                  <th className="py-3.5 px-6">Opportunity Service</th>
                  <th className="py-3.5 px-6">Estimated MRR / Value</th>
                  <th className="py-3.5 px-6">Deterministic Rationale</th>
                  <th className="py-3.5 px-6">Status</th>
                  <th className="py-3.5 px-6 text-right">Actions</th>
                </tr>
              </thead>
              <tbody className="divide-y divide-slate-100 dark:divide-slate-800">
                {upsells.length === 0 ? (
                  <tr>
                    <td colSpan={6} className="py-8 text-center text-slate-400">
                      No expansion opportunities identified yet. Complete delivery projects to trigger upsell suggestions.
                    </td>
                  </tr>
                ) : (
                  upsells.map((u) => (
                    <tr key={u.id} className="hover:bg-slate-50 dark:hover:bg-slate-800/30 transition-colors">
                      <td className="py-4 px-6 font-medium text-slate-900 dark:text-white">
                        {u.customer_name}
                      </td>
                      <td className="py-4 px-6">
                        <span className="px-2.5 py-1 text-xs font-semibold rounded-md bg-indigo-50 text-indigo-700 dark:bg-indigo-900/30 dark:text-indigo-300 border border-indigo-100 dark:border-indigo-800">
                          {u.service_type.replace('_', ' ')}
                        </span>
                      </td>
                      <td className="py-4 px-6 font-semibold text-slate-900 dark:text-white">
                        ₹{u.estimated_mrr.toLocaleString()}/mo
                        <span className="block text-xs font-normal text-slate-400">₹{u.estimated_value.toLocaleString()} ARR</span>
                      </td>
                      <td className="py-4 px-6 text-xs text-slate-500 max-w-xs">
                        {u.reason}
                      </td>
                      <td className="py-4 px-6">
                        <span className={`px-2 py-0.5 text-xs font-medium rounded-full ${
                          u.status === 'ACCEPTED'
                            ? 'bg-emerald-100 text-emerald-800 dark:bg-emerald-900/40 dark:text-emerald-300'
                            : u.status === 'PITCHED'
                            ? 'bg-blue-100 text-blue-800 dark:bg-blue-900/40 dark:text-blue-300'
                            : 'bg-slate-100 text-slate-700 dark:bg-slate-800 dark:text-slate-300'
                        }`}>
                          {u.status}
                        </span>
                      </td>
                      <td className="py-4 px-6 text-right space-x-2">
                        {u.status === 'IDENTIFIED' && (
                          <button
                            onClick={() => handleUpdateUpsellStatus(u.id, 'PITCHED')}
                            className="px-2.5 py-1 text-xs font-medium text-blue-600 hover:text-blue-700 bg-blue-50 dark:bg-blue-950/40 rounded border border-blue-200 dark:border-blue-800"
                          >
                            Pitch Deal
                          </button>
                        )}
                        {u.status !== 'ACCEPTED' && (
                          <button
                            onClick={() => handleUpdateUpsellStatus(u.id, 'ACCEPTED')}
                            className="px-2.5 py-1 text-xs font-medium text-emerald-600 hover:text-emerald-700 bg-emerald-50 dark:bg-emerald-950/40 rounded border border-emerald-200 dark:border-emerald-800"
                          >
                            Accept & Start Retainer
                          </button>
                        )}
                      </td>
                    </tr>
                  ))
                )}
              </tbody>
            </table>
          </div>
        </div>
      )}

      {/* New Retainer Modal */}
      {isRetainerModalOpen && (
        <div className="fixed inset-0 bg-slate-900/60 backdrop-blur-xs flex items-center justify-center p-4 z-50">
          <div className="bg-white dark:bg-slate-900 rounded-2xl max-w-lg w-full p-6 border border-slate-200 dark:border-slate-800 shadow-2xl space-y-5">
            <div className="flex justify-between items-center border-b border-slate-100 dark:border-slate-800 pb-3">
              <h3 className="text-lg font-bold text-slate-900 dark:text-white">
                Create Recurring Retainer Contract
              </h3>
              <button
                onClick={() => setIsRetainerModalOpen(false)}
                className="text-slate-400 hover:text-slate-600 text-xl font-bold"
              >
                ×
              </button>
            </div>

            <form onSubmit={handleCreateRetainer} className="space-y-4">
              <div>
                <label className="block text-xs font-semibold text-slate-600 dark:text-slate-300 uppercase tracking-wider mb-1">
                  Customer
                </label>
                <select
                  value={selectedCustomerId}
                  onChange={(e) => setSelectedCustomerId(e.target.value)}
                  className="w-full bg-slate-50 dark:bg-slate-800 border border-slate-200 dark:border-slate-700 rounded-lg p-2.5 text-sm text-slate-900 dark:text-white"
                  required
                >
                  {customers.map((c) => (
                    <option key={c.id} value={c.id}>
                      {c.company_name}
                    </option>
                  ))}
                </select>
              </div>

              <div>
                <label className="block text-xs font-semibold text-slate-600 dark:text-slate-300 uppercase tracking-wider mb-1">
                  Service Type
                </label>
                <select
                  value={serviceType}
                  onChange={(e) => setServiceType(e.target.value)}
                  className="w-full bg-slate-50 dark:bg-slate-800 border border-slate-200 dark:border-slate-700 rounded-lg p-2.5 text-sm text-slate-900 dark:text-white"
                >
                  <option value="SEO_RETAINER">SEO Retainer (Organic Rankings)</option>
                  <option value="SMMA_RETAINER">Social Media Management (SMMA)</option>
                  <option value="WEBSITE_MAINTENANCE">Website Maintenance & Security</option>
                  <option value="HOSTING_MAINTENANCE">Managed Cloud Hosting & Backups</option>
                  <option value="PAID_ADS_MANAGEMENT">Paid Ads Performance Management</option>
                </select>
              </div>

              <div className="grid grid-cols-2 gap-3">
                <div>
                  <label className="block text-xs font-semibold text-slate-600 dark:text-slate-300 uppercase tracking-wider mb-1">
                    Frequency
                  </label>
                  <select
                    value={billingFreq}
                    onChange={(e) => setBillingFreq(e.target.value)}
                    className="w-full bg-slate-50 dark:bg-slate-800 border border-slate-200 dark:border-slate-700 rounded-lg p-2.5 text-sm text-slate-900 dark:text-white"
                  >
                    <option value="MONTHLY">Monthly</option>
                    <option value="QUARTERLY">Quarterly</option>
                    <option value="ANNUAL">Annual</option>
                  </select>
                </div>
                <div>
                  <label className="block text-xs font-semibold text-slate-600 dark:text-slate-300 uppercase tracking-wider mb-1">
                    Billing Amount (₹)
                  </label>
                  <input
                    type="number"
                    value={billingAmount}
                    onChange={(e) => setBillingAmount(Number(e.target.value))}
                    className="w-full bg-slate-50 dark:bg-slate-800 border border-slate-200 dark:border-slate-700 rounded-lg p-2.5 text-sm text-slate-900 dark:text-white"
                    required
                  />
                </div>
              </div>

              <div>
                <label className="block text-xs font-semibold text-slate-600 dark:text-slate-300 uppercase tracking-wider mb-1">
                  Notes
                </label>
                <textarea
                  value={retainerNotes}
                  onChange={(e) => setRetainerNotes(e.target.value)}
                  rows={2}
                  className="w-full bg-slate-50 dark:bg-slate-800 border border-slate-200 dark:border-slate-700 rounded-lg p-2.5 text-sm text-slate-900 dark:text-white"
                  placeholder="e.g. Contract renewal includes 4 blog posts and weekly security audit."
                />
              </div>

              <div className="flex justify-end gap-3 pt-3 border-t border-slate-100 dark:border-slate-800">
                <button
                  type="button"
                  onClick={() => setIsRetainerModalOpen(false)}
                  className="px-4 py-2 text-sm text-slate-600 dark:text-slate-300 hover:bg-slate-100 dark:hover:bg-slate-800 rounded-lg"
                >
                  Cancel
                </button>
                <button
                  type="submit"
                  className="px-4 py-2 text-sm font-medium text-white bg-blue-600 hover:bg-blue-700 rounded-lg shadow-sm"
                >
                  Save Contract
                </button>
              </div>
            </form>
          </div>
        </div>
      )}
    </div>
  );
}
