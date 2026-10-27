// Safe date formatting without `new Date('YYYY-MM-DD')` to prevent UTC midnight shifts

const MONTH_NAMES = [
  'Jan', 'Feb', 'Mar', 'Apr', 'May', 'Jun',
  'Jul', 'Aug', 'Sep', 'Oct', 'Nov', 'Dec',
];

export function formatIstDate(dateStr: string): string {
  if (!dateStr || typeof dateStr !== 'string') return '';
  const parts = dateStr.split('-');
  if (parts.length < 3) return dateStr;

  const monthIdx = parseInt(parts[1], 10) - 1;
  const dayNum = parseInt(parts[2], 10);

  if (isNaN(monthIdx) || isNaN(dayNum) || monthIdx < 0 || monthIdx > 11) {
    return dateStr;
  }

  return `${dayNum} ${MONTH_NAMES[monthIdx]}`;
}

export function formatIstDateFull(dateStr: string): string {
  if (!dateStr || typeof dateStr !== 'string') return '';
  const parts = dateStr.split('-');
  if (parts.length < 3) return dateStr;

  const year = parts[0];
  const monthIdx = parseInt(parts[1], 10) - 1;
  const dayNum = parseInt(parts[2], 10);

  if (isNaN(monthIdx) || isNaN(dayNum) || monthIdx < 0 || monthIdx > 11) {
    return dateStr;
  }

  return `${dayNum} ${MONTH_NAMES[monthIdx]} ${year}`;
}
