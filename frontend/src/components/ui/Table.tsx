import type { ReactNode, TdHTMLAttributes, ThHTMLAttributes } from "react";

/** A data table that scrolls sideways on small screens instead of breaking the page.
 * The caption is read out by screen readers but not shown. */
export function Table({
  caption,
  head,
  children,
}: {
  caption: string;
  head: ReactNode;
  children: ReactNode;
}) {
  return (
    <div className="overflow-x-auto rounded-md border border-neutral-200">
      <table className="w-full text-left text-sm">
        <caption className="sr-only">{caption}</caption>
        <thead className="bg-neutral-50">
          <tr className="border-b border-neutral-200">{head}</tr>
        </thead>
        <tbody className="divide-y divide-neutral-200 bg-white">{children}</tbody>
      </table>
    </div>
  );
}

export function Th({ children, ...rest }: ThHTMLAttributes<HTMLTableCellElement>) {
  return (
    <th scope="col" className="px-3 py-2 text-xs font-medium text-neutral-500" {...rest}>
      {children}
    </th>
  );
}

export function Td({ children, ...rest }: TdHTMLAttributes<HTMLTableCellElement>) {
  return (
    <td className="px-3 py-2.5 align-middle text-neutral-800" {...rest}>
      {children}
    </td>
  );
}
