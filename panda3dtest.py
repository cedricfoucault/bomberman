from direct.showbase.ShowBase import ShowBase

class Test(ShowBase): 
    def __init__(self):
        ShowBase.__init__(self)
        floor = loader.loadModel("assets/plane")
        r,g,b,a = (1.0, 0.0, 0.0, 1.0)
        floor.setColor(r,g,b,a)
        floor.setScale(2.5, 2.5, 1)
        floor.setPos(1, 1, 0)
        floor.reparentTo(render)

        # wall_left = loader.loadModel(self.VIEWS['wall']['model'])
        # r,g,b,a = self.VIEWS['wall']['rgba']
        # wall_left.setColor(r,g,b,a)
        # wall_left.setScale(self.VIEWS['wall']['scale'], self.VIEWS['wall']['scale'] * (self.height + 2), 1)
        # wall_left.setPos(-1, self.height / 2, 0)
        # wall_left.reparentTo(render)

        base.disableMouse()
        camera.setPos(1, 1, 100)
        camera.setHpr(0, -90, 0)
        
if __name__ == "__main__":
    app = Test()
    app.run()
