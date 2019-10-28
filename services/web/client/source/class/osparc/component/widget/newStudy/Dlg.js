/* ************************************************************************

   osparc - the simcore frontend

   https://osparc.io

   Copyright:
     2018 IT'IS Foundation, https://itis.swiss

   License:
     MIT: https://opensource.org/licenses/MIT

   Authors:
     * Odei Maiz (odeimaiz)

************************************************************************ */

/**
 * Widget that provides the form for creating a new study
 *
 * After doing some Study title validation the following data event is fired:
 * <pre class='javascript'>
 *   {
 *     prjTitle: title,
 *     prjDescription: desc,
 *     prjTemplateId: templ
 *   };
 * </pre>
 *
 * *Example*
 *
 * Here is a little example of how to use the widget.
 *
 * <pre class='javascript'>
 *   let newStudyDlg = new osparc.component.widget.newStudy.Dlg();
 *   this.getRoot().add(newStudyDlg);
 * </pre>
 */

qx.Class.define("osparc.component.widget.newStudy.Dlg", {
  extend: qx.ui.core.Widget,

  construct: function(template=null) {
    this.base(arguments);

    var scroller = new qx.ui.container.Scroll();

    var container = new qx.ui.container.Composite(new qx.ui.layout.VBox(10));
    container.setPadding(20);
    container.setAllowStretchX(false);

    scroller.add(container);

    this.add(scroller, {
      edge: 0
    });

    container.add(this.__getBlank(template));
    container.add(this.__getWithPipeline());
    container.add(this.__getWithToken());
  },

  events: {
    "createStudy": "qx.event.type.Data"
  },

  members: {
    __getBlank: function(template) {
      const newBlankStudy = new osparc.component.widget.newStudy.Blank(template);
      newBlankStudy.addListener("createStudy", e => {
        this.fireDataEvent("createStudy", e.getData());
      }, this);
      return newBlankStudy;
    },

    __getWithPipeline: function(template) {
      const newBlankStudy = new osparc.component.widget.newStudy.WithPipeline(template);
      newBlankStudy.addListener("createStudy", e => {
        this.fireDataEvent("createStudy", e.getData());
      }, this);
      return newBlankStudy;
    },

    __getWithToken: function(template) {
      const newBlankStudy = new osparc.component.widget.newStudy.WithToken(template);
      newBlankStudy.addListener("createStudy", e => {
        this.fireDataEvent("createStudy", e.getData());
      }, this);
      return newBlankStudy;
    }
  }
});
