/* ************************************************************************

   osparc - an entry point to oSparc

   https://osparc.io

   Copyright:
     2023 IT'IS Foundation, https://itis.swiss

   License:
     MIT: https://opensource.org/licenses/MIT

   Authors:
     * Odei Maiz (odeimaiz)

************************************************************************ */

qx.Class.define("osparc.product.landingPage.s4llite.solutions.SolutionsBase", {
  extend: qx.ui.core.Widget,
  type: "abstract",

  construct: function() {
    this.base(arguments);

    this._setLayout(new qx.ui.layout.VBox(40).set({
      alignX: "center",
      alignY: "middle"
    }));

    this.setPadding(30);

    this.buildLayout();
  },

  statics: {
    createSolutionHeader: function(title, description) {
      const headerLayout = new qx.ui.container.Composite(new qx.ui.layout.VBox(20).set({
        alignX: "center",
        alignY: "middle"
      })).set({
        width: 450,
        maxWidth: 450
      });

      const text1 = new qx.ui.basic.Label().set({
        value: title,
        font: "text-26",
        rich: true,
        wrap: true
      });
      headerLayout.add(text1);

      const text2 = new qx.ui.basic.Label().set({
        value: description,
        font: "text-18",
        rich: true,
        wrap: true
      });
      headerLayout.add(text2);

      const label = qx.locale.Manager.tr("Request a Demo");
      const linkButton = this.mediumStrongButton(label);
      linkButton.getContentElement().setStyles({
        "border-radius": "8px"
      });
      linkButton.addListener("tap", () => window.open("https://zmt.swiss/", "_blank"));
      headerLayout.add(linkButton);

      return headerLayout;
    },

    mediumStrongButton: function(label, strong = true) {
      const button = new qx.ui.form.Button().set({
        label,
        font: "text-16",
        center: true,
        padding: 12,
        allowGrowX: false,
        width: 170
      });
      if (strong) {
        button.setAppearance("strong-button");
      }
      button.getContentElement().setStyles({
        "border-radius": "8px"
      });
      return button;
    },

    createContent: function(title, description, imageSrc, imagePos = "left") {
      const contentLayout = new qx.ui.container.Composite(new qx.ui.layout.HBox(80).set({
        alignX: "center",
        alignY: "middle"
      }));

      const textLayout = new qx.ui.container.Composite(new qx.ui.layout.VBox(30).set({
        alignY: "middle"
      })).set({
        maxWidth: 450
      });

      const titleLabel = new qx.ui.basic.Label().set({
        value: title,
        font: "text-18",
        rich: true,
        wrap: true
      });
      textLayout.add(titleLabel);

      const descLabel = new qx.ui.basic.Label().set({
        value: description,
        font: "text-16",
        rich: true,
        wrap: true
      });
      textLayout.add(descLabel);

      const label = qx.locale.Manager.tr("Learn More");
      const learnMoreButton = this.mediumStrongButton(label, false);
      learnMoreButton.getContentElement().setStyles({
        "border-radius": "8px"
      });
      textLayout.add(learnMoreButton);

      const image = new qx.ui.basic.Image(imageSrc).set({
        alignY: "middle",
        scale: true
      });
      image.getContentElement().setStyles({
        "border-radius": "8px"
      });

      if (imagePos === "left") {
        contentLayout.add(image, {
          width: "50%"
        });
        contentLayout.add(textLayout, {
          width: "50%"
        });
      } else {
        contentLayout.add(textLayout, {
          width: "50%"
        });
        contentLayout.add(image, {
          width: "50%"
        });
      }

      return contentLayout;
    }
  },

  members: {
    buildLayout: function() {
      throw new Error("Abstract method called!");
    }
  }
});
