/* ************************************************************************

   qxapp - the simcore frontend

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
 *   const url = qxapp.component.widget.NewGHIssue.getNewIssueUrl();
 *   window.open(url);
 * </pre>
 */

qx.Class.define("qxapp.component.widget.NewGHIssue", {
  type: "static",

  statics: {
    getNewIssueUrl: function() {
      const env = JSON.stringify(qxapp.component.widget.NewGHIssue.getEnv());
      const temp = qxapp.component.widget.NewGHIssue.getTemplate();
      const body = encodeURIComponent(temp+env);
      const url = "https://github.com/ITISFoundation/osparc-simcore/issues/new?labels=tester_review&body=" + body;
      return url;
    },

    getEnv: function() {
      let libs = [];
      [
        qxapp.utils.LibVersions.getPlatformVersion,
        qxapp.utils.LibVersions.getUIVersion,
        qxapp.utils.LibVersions.getQxCompiler,
        qxapp.utils.LibVersions.getQxLibraryInfoMap,
        qxapp.utils.LibVersions.get3rdPartyLibs
      ].forEach(lib => {
        libs = libs.concat(lib.call(this));
      }, this);

      return libs;
    },

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

## Your environment
`;
    }
  }
});
