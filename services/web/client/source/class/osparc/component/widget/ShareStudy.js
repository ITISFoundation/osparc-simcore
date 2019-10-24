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


      const box11 = new qx.ui.groupbox.GroupBox(this.tr("Copy Study"));
      box11.setLayout(new qx.ui.layout.HBox(5));
      const shareStudyCopyTF = new qx.ui.form.TextField().set({
        readOnly: true
      });
      box11.add(shareStudyCopyTF, {
        flex: 1
      });
      const copyLinkBtn1 = new qx.ui.form.Button(this.tr("Copy Link"));
      copyLinkBtn1.addListener("execute", function() {
        const shareStudyCopyToken = shareStudyCopyTF.getValue();
        osparc.utils.Utils.copyTextToClipboard(shareStudyCopyToken);
        shareStudyCopyTF.selectAllText();
      });
      box11.add(copyLinkBtn1);
      box1.add(box11);


      const box12 = new qx.ui.groupbox.GroupBox(this.tr("Share Study")).set({
        enabled: false
      });
      box12.setLayout(new qx.ui.layout.HBox(5));
      const shareStudyShareTF = new qx.ui.form.TextField().set({
        readOnly: true
      });
      box12.add(shareStudyShareTF, {
        flex: 1
      });
      const copyLinkBtn2 = new qx.ui.form.Button(this.tr("Copy Link"));
      copyLinkBtn2.addListener("execute", function() {
        const shareStudyCopyToken = shareStudyShareTF.getValue();
        osparc.utils.Utils.copyTextToClipboard(shareStudyCopyToken);
        shareStudyShareTF.selectAllText();
      });
      box12.add(copyLinkBtn2);
      box1.add(box12);

      shareStudyLayout.add(box1);

      const params = {
        url: {
          "study_id": studyModel.getUuid()
        }
      };
      osparc.data.Resources.getOne("shareStudy", params)
        .then(tokensList => {
          shareStudyCopyTF.setValue(tokensList["copy"]);
          shareStudyShareTF.setValue(tokensList["share"]);
        })
        .catch(err => console.error(err));

      this._add(shareStudyLayout, {
        top: 10,
        right: 10,
        bottom: 10,
        left: 10
      });
    }
  }
});
