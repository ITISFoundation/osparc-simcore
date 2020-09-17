/* ************************************************************************

   osparc - the simcore frontend

   https://osparc.io

   Copyright:
     2019 IT'IS Foundation, https://itis.swiss

   License:
     MIT: https://opensource.org/licenses/MIT

   Authors:
     * Odei Maiz (odeimaiz)

************************************************************************ */

/**
 * Here is a little example of how to use the widget.
 *
 * <pre class='javascript'>
 *   const url = osparc.utils.NewGHIssue.getNewIssueUrl();
 *   window.open(url);
 * </pre>
 */

qx.Class.define("osparc.utils.NewIssueBase", {
  type: "static",

  statics: {
    getTemplate: function() {
      return `
## Long story short
<!-- Please describe your review or bug you found. -->

## Expected behaviour
<!-- What is the behaviour you expect? -->

## Actual behaviour
<!-- What's actually happening? -->

## Steps to reproduce
<!-- Please describe steps to reproduce the issue. -->

Note: your environment was attached but will not be displayed
<!--
## Your environment
`;
    },

    getScreenResolution: function() {
      return {
        "screenResolution": {
          "width": window.screen.width,
          "height": window.screen.height
        }
      };
    }
  }
});
