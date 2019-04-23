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
 *   let newGHIssue = new qxapp.component.widget.NewGHIssue();
 *   this.getRoot().add(newGHIssue);
 * </pre>
 */

qx.Class.define("qxapp.component.widget.NewGHIssue", {
  extend: qx.ui.core.Widget,

  construct: function() {
    this.base(arguments);

    this._setLayout(new qx.ui.layout.VBox(5));

    this.__createSteps();
    this._add(new qx.ui.core.Spacer(null, 10));
    this.__createGHLinkButton();
    this.__createCopyEnvButton();
  },

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
      return " \
## Long story short\n \
<!-- Please describe your review or bug you found. -->\n \
\n \
## Expected behaviour\n \
<!-- What is the behaviour you expect? -->\n \
\n \
## Actual behaviour\n \
<!-- What's actually happening? -->\n \
\n \
## Steps to reproduce\n \
<!-- Please describe steps to reproduce the issue. -->\n \
\n \
## Your environment\n";
    }
  },

  members: {
    __issueTitle: null,
    __issueDescription: null,
    __mdEditor: null,

    __createSteps: function() {
      [
        this.tr("Follow these steps to Open a New Issue:"),
        this.tr("1) Press the 'Copy environment information' button. This will copy some relevant environment information to the clipboard."),
        this.tr("2) Press the 'Open New Issue' button. This will open a 'Open New Issue' tab in GitHub."),
        this.tr("3) In GitHub, in the '## Your environment' section, paste what have been automaticaly copied"),
        this.tr("4) Fill up the information about the issue.")
      ].forEach(step => {
        const label = this.__createHelpLabel(step);
        this._add(label);
      });
    },

    __createHelpLabel: function(message=null) {
      const label = new qx.ui.basic.Label().set({
        value: message,
        rich : true,
        font : qx.bom.Font.fromConfig(qxapp.theme.Font.fonts["text-14"])
      });
      return label;
    },

    __createCopyEnvButton: function() {
      const copyEnvBtn = new qx.ui.form.Button(this.tr("Copy environment information")).set({
        allowGrowX: false
      });
      copyEnvBtn.addListener("execute", () => {
        const env = JSON.stringify(qxapp.component.widget.NewGHIssue.getEnv());
        if (qxapp.utils.Utils.copyTextToClipboard(env)) {
          copyEnvBtn.addState("hovered");
        }
      }, this);
      this._add(copyEnvBtn);
    },

    __createGHLinkButton: function() {
      const url = qxapp.component.widget.NewGHIssue.getNewIssueUrl();
      const toNewIssue = new qxapp.component.widget.LinkButton(this.tr("Open New Issue"), url);
      this._add(toNewIssue);
    }
  }
});
