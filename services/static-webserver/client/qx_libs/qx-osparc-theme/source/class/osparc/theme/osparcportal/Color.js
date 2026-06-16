/* ************************************************************************

  Sparc Portal Theme for Qooxdoo

  Copyright:
     2020 IT'IS Foundation

  License:
     MIT: https://opensource.org/licenses/MIT
     See the LICENSE file in the project's top-level directory for details.

  Authors:
    * Odei Maiz (odeimaiz)

  Origin:
    This theme is based in large parts on the the Simple
    theme included with Qooxdoo.
************************************************************************ */
/**
 * Based on osparcdark inverted colors
 */
qx.Theme.define("osparc.theme.osparcportal.Color", {
  extend: osparc.theme.osparcblue.Color,

  colors: {
    // ----------------- GAZELLE-CX -----------------
    // Primary Colors
    "gzl-primary-1": "#8300BF", // Repeating major elements across the site like links and buttons
    "gzl-primary-2": "#24245B", // Repeating major elements across the site like heroes and header text
    "gzl-primary-3": "#60626C", // Typography and icons (bug in original document)

    // Secondary Colors
    "gzl-secondary-1": "#BC00FC", // Decorative elements such as illustrations (bug in original document)
    "gzl-secondary-2": "#0026FF", // Decorative elements such as illustrations

    // Status Colors
    "gzl-status-success": "#00E66B", // Confirmation messages
    "gzl-status-warning": "#FF8400", // To warn users of potentially harmful situation
    "gzl-status-error": "#b51d09", // Error messages and confirmation for deletion

    // Text Colors
    "gzl-text-body": "#303133", // Body text
    "gzl-text-footer": "#606266", // Footer text
    "gzl-text-ghost": "#909399", // Labels and ghost text

    // Line Colors
    "gzl-line-card": "#DCDFE6", // Cards
    "gzl-line-dividers": "#E4E7ED", // Table dividers/breadcrumb backgrounds

    // Background Colors
    // "gzl-background": "#F5F7FA",
    "gzl-background": "#FFFFFF",
    // ----------------- GAZELLE-CX -----------------

    "secondary-3": "#909399",


    // main
    "background-main": "gzl-background",
    "primary-color": "gzl-primary-1",
    "primary-color-light": "gzl-primary-3",
    "primary-color-dark": "gzl-primary-2",
    "secondary-color": "gzl-secondary-2",
    "secondary-color-light": "secondary-3",
    "secondary-color-dark": "gzl-secondary-1",
    "contrasted-background": "gzl-background",
    "invalid-color": "gzl-status-error",
    "text": "gzl-text-body",
    "text-disabled": "gzl-text-ghost",
    "text-selected": "#FFFFFF",
    "text-placeholder": "gzl-text-ghost",
    "text-darker": "gzl-text-ghost",
    "contrasted-text-dark": "gzl-line-dividers",
    "contrasted-text-light": "gzl-text-body"
  }
});
