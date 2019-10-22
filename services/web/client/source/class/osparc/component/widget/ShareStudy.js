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
 * Widget that provides the form for sharing a study
 *
 * *Example*
 *
 * Here is a little example of how to use the widget.
 *
 * <pre class='javascript'>
 *   const shareStudy = new osparc.component.widget.ShareStudy(study);
 *   this.getRoot().add(shareStudy);
 * </pre>
 */

qx.Class.define("osparc.component.widget.ShareStudy", {
  extend: qx.ui.core.Widget,

  construct: function(studyModel) {
    this.base(arguments);

    this._setLayout(new qx.ui.layout.Canvas());

    this.__createLayout(studyModel);
  },

  members: {
    __createLayout: function(studyModel) {
      const shareStudyLayout = new qx.ui.container.Composite(new qx.ui.layout.VBox(5));

      const box1 = new qx.ui.groupbox.GroupBox(this.tr("Link Sharing"));
      box1.setLayout(new qx.ui.layout.VBox(5));

      const box11 = new qx.ui.groupbox.GroupBox(this.tr("Clone Study"));
      box11.setLayout(new qx.ui.layout.HBox(5));
      let myLink = window.location.href;
      myLink += "study/" + studyModel.getUuid();
      const myLinkTF = new qx.ui.form.TextField(myLink).set({
        readOnly: true
      });
      box11.add(myLinkTF, {
        flex: 1
      });
      const copyLinkBtn = new qx.ui.form.Button(this.tr("Copy Link"));
      copyLinkBtn.addListener("execute", function() {
        osparc.utils.Utils.copyTextToClipboard(myLink);
      });
      box11.add(copyLinkBtn);
      box1.add(box11);

      shareStudyLayout.add(box1);

      const box2 = new qx.ui.groupbox.GroupBox(this.tr("Share Study")).set({
        enabled: false
      });
      box2.setLayout(new qx.ui.layout.VBox(5));
      shareStudyLayout.add(box2);

      this._add(shareStudyLayout, {
        top: 10,
        right: 10,
        bottom: 10,
        left: 10
      });
    }
  }
});
