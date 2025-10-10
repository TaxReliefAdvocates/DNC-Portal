import React from 'react'

export const StatusBadge: React.FC<{ status: 'pending'|'in_progress'|'success'|'failed'|'approved'|'denied'|'completed'|'skipped'; className?: string }>
  = ({ status, className }) => {
  const map: Record<string, string> = {
    pending: 'bg-gray-100 text-gray-800 border border-gray-300',
    in_progress: 'bg-blue-100 text-blue-800 border border-blue-300',
    success: 'bg-green-100 text-green-800 border border-green-300',
    failed: 'bg-red-100 text-red-800 border border-red-300',
    approved: 'bg-green-100 text-green-800 border border-green-300',
    denied: 'bg-red-100 text-red-800 border border-red-300',
    completed: 'bg-green-100 text-green-800 border border-green-300',
    skipped: 'bg-gray-100 text-gray-700 border border-gray-300',
  }
  return (
    <span className={`px-2 py-0.5 rounded text-xs font-medium ${map[status]} ${className||''}`}>{
      status.replace('_', ' ')
    }</span>
  )
}


