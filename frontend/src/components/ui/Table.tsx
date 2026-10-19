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
    <div className="overflow-x-auto">
      <table className="w-full text-left text-sm">
        <caption className="sr-only">{caption}</caption>
        <thead>
          <tr className="border-b border-neutral-200">{head}</tr>
        </thead>
        <tbody className="divide-y divide-neutral-200">{children}</tbody>
      </table>
    </div>
  );
}

export function Th({ children, ...rest }: ThHTMLAttributes<HTMLTableCellElement>) {
  return (
    <th
      scope="col"
      className="py-2 pr-4 text-xs font-medium tracking-wide text-neutral-500 uppercase"
      {...rest}
    >
      {children}
    </th>
  );
}

export function Td({ children, ...rest }: TdHTMLAttributes<HTMLTableCellElement>) {
  return (
    <td className="py-3 pr-4 align-middle text-neutral-700" {...rest}>
      {children}
    </td>
  );
}
