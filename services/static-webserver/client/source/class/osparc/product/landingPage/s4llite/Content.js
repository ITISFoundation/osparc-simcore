/* ************************************************************************

   osparc - an entry point to oSparc

   https://osparc.io

   Copyright:
     2020 IT'IS Foundation, https://itis.swiss

   License:
     MIT: https://opensource.org/licenses/MIT

   Authors:
     * Odei Maiz (odeimaiz)

************************************************************************ */

qx.Class.define("osparc.product.landingPage.s4llite.Content", {
  extend: qx.ui.core.Widget,

  construct: function() {
    this.base(arguments);

    this._setLayout(new qx.ui.layout.VBox(80).set({
      alignX: "center",
      alignY: "middle"
    }));

    this.setPadding(50);

    this.buildLayout();
  },

  members: {
    buildLayout: function() {
      const content1 = this.__createContent1();
      this._add(content1);

      const content2 = this.__createContent2();
      this._add(content2);

      const content3 = this.__createContent3();
      this._add(content3);

      const content4 = this.__createContent4();
      this._add(content4);
    },

    __createContent1: function() {
      const contentLayout = new qx.ui.container.Composite(new qx.ui.layout.HBox(50).set({
        alignX: "center",
        alignY: "middle"
      }));

      const leftLayout = new qx.ui.container.Composite(new qx.ui.layout.VBox(20).set({
        alignX: "center",
        alignY: "middle"
      })).set({
        width: 450,
        maxWidth: 450
      });

      const text1 = new qx.ui.basic.Label().set({
        value: this.tr("Revolutionary simulation platform, combining computable human phantoms with the most powerful physics solvers and the most advanced tissue models"),
        font: "text-24",
        rich: true,
        wrap: true
      });
      leftLayout.add(text1);

      const text2 = new qx.ui.basic.Label().set({
        value: this.tr("Directly analyzing biological real-world phenomena and complex technical devices in a validated biological and anatomical environment, it also offers leading performance with all the features expected from a multiphysics CAE/TCAD platform."),
        font: "text-16",
        rich: true,
        wrap: true
      });
      leftLayout.add(text2);

      const tryItOutButton = new qx.ui.form.Button().set({
        appearance: "strong-button",
        label: this.tr("Try it out"),
        font: "text-18",
        center: true,
        padding: 20,
        allowGrowX: false,
        width: 180
      });
      tryItOutButton.getContentElement().setStyles({
        "border-radius": "8px"
      });
      leftLayout.add(tryItOutButton);

      contentLayout.add(leftLayout, {
        width: "50%"
      });

      const image = new qx.ui.basic.Image().set({
        source: "https://raw.githubusercontent.com/ZurichMedTech/s4l-assets/main/app/lite/extra/bunny.png",
        scale: true,
        alignX: "center",
        maxWidth: 400,
        maxHeight: 300
      });
      contentLayout.add(image, {
        width: "50%"
      });

      return contentLayout;
    },

    __createContent2: function() {
      const contentLayout = new qx.ui.container.Composite(new qx.ui.layout.VBox(20).set({
        alignX: "center",
        alignY: "middle"
      }));

      const text1 = new qx.ui.basic.Label().set({
        value: this.tr("Trusted by 100+ users"),
        font: "text-16",
        width: 160,
        rich: true,
        wrap: true
      });
      contentLayout.add(text1);

      const usersLayout = new qx.ui.container.Composite(new qx.ui.layout.HBox(10).set({
        alignX: "center",
        alignY: "middle"
      }));

      const size = 48;
      [{
        user: "https://github.com/AntoninoMarioC",
        avatar: "https://avatars.githubusercontent.com/u/34208500"
      }, {
        user: "https://github.com/drniiken",
        avatar: "https://avatars.githubusercontent.com/u/32800795"
      }, {
        user: "https://github.com/elisabettai",
        avatar: "https://avatars.githubusercontent.com/u/18575092"
      }, {
        user: "https://github.com/GitHK",
        avatar: "https://avatars.githubusercontent.com/u/5694077"
      }, {
        user: "https://github.com/ignapas",
        avatar: "https://avatars.githubusercontent.com/u/4764217"
      }, {
        user: "https://github.com/mrnicegyu11",
        avatar: "https://avatars.githubusercontent.com/u/8209087"
      }, {
        user: "https://github.com/mguidon",
        avatar: "https://avatars.githubusercontent.com/u/33161876"
      }, {
        user: "https://github.com/matusdrobuliak66",
        avatar: "https://avatars.githubusercontent.com/u/60785969"
      }, {
        user: "https://github.com/odeimaiz",
        avatar: "https://avatars.githubusercontent.com/u/33152403"
      }, {
        user: "https://github.com/pcrespov",
        avatar: "https://avatars.githubusercontent.com/u/32402063"
      }, {
        user: "https://github.com/sanderegg",
        avatar: "https://avatars.githubusercontent.com/u/35365065"
      }, {
        user: "https://github.com/Surfict",
        avatar: "https://avatars.githubusercontent.com/u/4354348"
      }].forEach(user => {
        const link = user.avatar + "?s=" + size;
        const image = new qx.ui.basic.Image().set({
          source: link,
          scale: true,
          maxWidth: size,
          maxHeight: size,
          cursor: "pointer"
        });
        image.addListener("tap", () => window.open(user.user, "_blank"));
        image.getContentElement().setStyles({
          "border-radius": "16px"
        });
        usersLayout.add(image);
      });
      contentLayout.add(usersLayout);

      return contentLayout;
    },

    __createTabPage: function(title, imageSrc, text) {
      const page = new qx.ui.tabview.Page(title);
      page.setLayout(new qx.ui.layout.HBox(10));
      const tabButton = page.getChildControl("button");
      tabButton.set({
        alignX: "right"
      });
      tabButton.getChildControl("label").set({
        font: "text-16",
        textAlign: "right",
        alignX: "right",
        width: 220
      });
      const image = new qx.ui.basic.Image(imageSrc).set({
        width: 600,
        height: 350,
        scale: true
      });
      page.add(image);
      const label = new qx.ui.basic.Label(text).set({
        font: "text-16",
        width: 200,
        rich: true,
        wrap: true,
        alignY: "middle"
      });
      page.add(label);
      return page;
    },

    __createContent3: function() {
      const contentLayout = new qx.ui.container.Composite(new qx.ui.layout.VBox(20).set({
        alignX: "center",
        alignY: "middle"
      }));

      const text1 = new qx.ui.basic.Label().set({
        value: this.tr("Access, run and share simulations in the cloud from any browser"),
        font: "text-24",
        textAlign: "center",
        width: 360,
        rich: true,
        wrap: true
      });
      contentLayout.add(text1);

      const tabs = new qx.ui.tabview.TabView().set({
        contentPadding: 20,
        barPosition: "left",
        allowGrowX: false,
        alignX: "center"
      });
      [{
        title: "Cloud-Native",
        image: "https://www.simscale.com/wp-content/uploads/2022/11/e-motor-cooling-simulation-with-webside-laptop-and-computer-1.png",
        text: "No VPN, No remote desktop. True SaaS with instant access anywhere & anytime from a browser without any special hardware."
      }, {
        title: "One Platform, broad Physics",
        image: "https://www.simscale.com/wp-content/uploads/2022/11/multiple-physics-simulations-laptop.gif",
        text: "No disconnected tools used in silos. A single platform with broad physics capabilities for both rough early- and detailed late-stage simulations."
      }, {
        title: "Real-time Collaboration",
        image: "https://www.simscale.com/wp-content/uploads/2022/11/e-motor-cooling-simulation-with-users-laptop.png",
        text: "Google-Docs-style collaboration built-in, enabling unparalleled in-app support as well as sharing simulations with colleagues."
      }, {
        title: "Any Scale",
        image: "https://www.simscale.com/wp-content/uploads/2022/12/e-motor-cooling-simulation-with-simulation-runs-laptop.png",
        text: "Practically no limits to simulation size, number of parallel simulations and storage. From one-off runs to programmatic design space exploration."
      }, {
        title: "Cost-effective",
        image: "https://www.simscale.com/wp-content/uploads/2022/11/pricing-page-laptop-1.png",
        text: "Capex-free, low ‘total cost of ownership’. Economically viable from a single user to 100s of seats. "
      }].forEach(tab => {
        const tabPage = this.__createTabPage(tab.title, tab.image, tab.text);
        tabs.add(tabPage);
      });
      let i = 0;
      const children = tabs.getChildren();
      setInterval(() => {
        tabs.setSelection([children[i]]);
        i++;
        if (i === children.size) {
          i = 0;
        }
      }, 5000);
      contentLayout.add(tabs);

      return contentLayout;
    },

    __createStep: function(imageSrc, title, text) {
      const stepLayout = new qx.ui.container.Composite(new qx.ui.layout.VBox(20).set({
        alignX: "center",
        alignY: "middle"
      }));
      const image = new qx.ui.basic.Image(imageSrc).set({
        width: 325,
        height: 230,
        scale: true
      });
      stepLayout.add(image);
      const labelTitle = new qx.ui.basic.Label(title).set({
        font: "text-20",
        alignText: "center",
        width: 200,
        rich: true,
        wrap: true
      });
      stepLayout.add(labelTitle);
      const labelText = new qx.ui.basic.Label(text).set({
        font: "text-16",
        alignText: "center",
        width: 200,
        rich: true,
        wrap: true
      });
      stepLayout.add(labelText);
      return stepLayout;
    },

    __createContent4: function() {
      const contentLayout = new qx.ui.container.Composite(new qx.ui.layout.VBox(20).set({
        alignX: "center",
        alignY: "middle"
      }));

      const text1 = new qx.ui.basic.Label().set({
        value: this.tr("HOW IT WORKS"),
        font: "text-18",
        textAlign: "center",
        width: 360,
        rich: true,
        wrap: true
      });
      contentLayout.add(text1);

      const text2 = new qx.ui.basic.Label().set({
        value: this.tr("Well separated contexts, we have three tabs/buttons, my friend"),
        font: "text-24",
        textAlign: "center",
        width: 360,
        rich: true,
        wrap: true
      });
      contentLayout.add(text2);

      const stepsLayout = new qx.ui.container.Composite(new qx.ui.layout.HBox(20).set({
        alignX: "center",
        alignY: "middle"
      }));
      [{
        image: "https://www.simscale.com/wp-content/uploads/2023/01/step-1-cad-import.png",
        title: "Modeling",
        text: "Upload, import CAD models or build your own model with our amazing tools"
      }, {
        image: "https://www.simscale.com/wp-content/uploads/2023/01/step-2-simulation-setup.png",
        title: "Simulation",
        text: "Define physics and run simulation in the cloud"
      }, {
        image: "https://www.simscale.com/wp-content/uploads/2023/01/step-3-design-decision.png",
        title: "Post Processing",
        text: "Review results and make better design decisions earlier, we also have a PP Calc"
      }].forEach(tab => {
        const tabPage = this.__createStep(tab.image, tab.title, tab.text);
        stepsLayout.add(tabPage);
      });
      contentLayout.add(stepsLayout);

      return contentLayout;
    }
  }
});
