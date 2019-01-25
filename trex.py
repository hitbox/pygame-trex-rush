import argparse
import contextlib
import copy
import json
import logging
import math
import os
import random
from pathlib import Path

from itertools import cycle

with contextlib.redirect_stdout(open(os.devnull, "w")):
    import pygame as pg

SCENE_EVENT = pg.USEREVENT
SCREEN_SIZE = (1024, 400)
FRAMERATE = 60
SCROLL_STEP = -6.0
SPRITE_SHEET_FILENAME = 'images/sprites.png'
SPRITE_SHEET = None
SPRITE_CELLS_FILENAME = 'cells.json'
SPRITE_CELLS = None

def init():
    global SPRITE_SHEET, SPRITE_CELLS
    SPRITE_CELLS = json.load(open(SPRITE_CELLS_FILENAME))
    SPRITE_SHEET = pg.image.load(SPRITE_SHEET_FILENAME)
    SPRITE_CELLS = {
        key: {
            cellkey: SPRITE_SHEET.subsurface(pg.Rect(*rectargs))
            for cellkey, rectargs in subdict.items()
        }
        for key, subdict in SPRITE_CELLS.items()
    }

def get_spritecell(x, y, w, h):
    return SPRITE_SHEET.subsurface(pg.Rect(x, y, w, h))

def random_choice_iter(possible):
    while True:
        yield random.choice(possible)

class Animation:

    def __init__(self, images, repeat=1):
        self.images = images
        self.repeat = repeat
        self._iter = cycle(self.images)
        self._frame = next(self._iter)
        self._repeat = self.repeat

    def __iter__(self):
        return self

    def __next__(self):
        if self._repeat == 0:
            self._repeat = self.repeat
            self._frame = next(self._iter)
        self._repeat -= 1
        return self._frame


class shared:

    enable_enemies = True
    shown_banner = False
    screen = None
    scrollspeed = None
    messages = None
    logo = None
    shown_banner = None
    score = None
    dino = None
    floor = None
    enemies = None
    sky = None
    ground = None
    logger = None


class Surface(pg.Surface):

    def __init__(self, size, flags=pg.SRCALPHA):
        super().__init__(size, flags=flags)


class ImageSprite(pg.sprite.Sprite):

    def __init__(self, image, *groups, position=None):
        super().__init__(*groups)
        self.image = image
        if position is None:
            position = {}
        self.rect = self.image.get_rect(**position)


class MovingTile(ImageSprite):

    def __init__(self, image, *groups, position=None):
        super().__init__(image, *groups, position=position)
        self.x = self.rect.x

    def update(self, dt):
        self.x += SCROLL_STEP
        self.rect.x = self.x


class GroundTile(MovingTile):
    pass


class Cactus(MovingTile):

    def __init__(self, *groups, position=None):
        cells = SPRITE_CELLS['cacti'].values()
        image = random.choice(tuple(cells))
        super().__init__(image, *groups, position=position)


class Dactyl(MovingTile):

    def __init__(self, *groups, position=None):
        cells = SPRITE_CELLS['dactyl']
        self.animation = Animation([cells['flying1'], cells['flying2']], repeat=8)
        super().__init__(next(self.animation), *groups, position=position)

    def update(self, dt):
        super().update(dt)
        self.image = next(self.animation)


EnemyClasses = [Cactus, Dactyl]

class Sprite(pg.sprite.Sprite):

    def __init__(self, *groups, position=None):
        super().__init__(*groups)
        self.enabled = True


class Cloud(Sprite):

    def __init__(self, **spritekwargs):
        spritekwargs.setdefault('image', SPRITE_CELLS['clouds']['cloud'])
        super().__init__(**spritekwargs)


class Logo(Sprite):

    def __init__(self, centerx, **spritekwargs):
        spritekwargs.setdefault('image', SPRITE_CELLS['text']['logo'])
        super().__init__(**spritekwargs)
        self.centerx = centerx
        self.vx = 80
        self.ax = -3.0
        self.state = 'slideon'
        self.elapsed = 0

    def update(self, dt):
        if self.state == 'slideon':
            # logo is sliding onto screen from left
            if self.vx < 0 and self.rect.centerx <= self.centerx:
                # accel has reversed direction and reached the center or
                # further left
                self.stop()
                self.x = self.centerx
                self.state = 'idle'
        elif self.state == 'idle':
            # logo sits in the center for a while
            self.elapsed += dt
            if self.elapsed > 1000:
                # time is up, slide logo off to right
                self.state = 'slideoff'
                self.vx = 40
                self.ax = -3.0
        elif self.state == 'slideoff':
            # logo is sliding off to left
            if self.rect.right < shared.screen.rect.left:
                # logo is off screen, kill it
                self.kill()
        super().update(dt)


class Score(Sprite):

    def __init__(self, *groups, position=None):
        super().__init__(*groups)
        self.value = 0
        widest = max(SPRITE_CELLS['text'][c].get_rect().width for c in '0123456789')
        self.rect = pg.Rect(0, 0, widest*4, 100)
        if position:
            for key, value in position.items():
                setattr(self.rect, key, value)
        self.elapsed = 0
        self.delay = 1000
        self._cache = {}

    def _update_cache(self, s):
        images = [SPRITE_CELLS['text'][c] for c in s]
        rects = [image.get_rect() for image in images]
        bigrect = pg.Rect(0,0,sum(rect.width for rect in rects),max(rect.height for rect in rects))
        surface = Surface(bigrect.size)
        items = zip(images, rects)
        prev = bigrect.copy()
        prev.topright = bigrect.topleft
        for image, rect in zip(images, rects):
            rect.topleft = prev.topright
            surface.blit(image, rect)
            prev = rect
        self._cache[s] = surface

    @property
    def image(self):
        s = '%04d' % self.value
        if not s in self._cache:
            self._update_cache(s)
        return self._cache[s]

    @image.setter
    def image(self, value):
        return

    def update(self, dt):
        if not self.enabled:
            return
        shared.logger.debug('%s: update', self)
        super().update(dt)
        self.elapsed += dt
        if self.elapsed >= self.delay:
            self.value += 1
            self.elapsed %= self.delay


class AnimatedMixin:

    @property
    def image(self):
        return self.animation.frame.image

    @image.setter
    def image(self, value):
        return

    @property
    def mask(self):
        return self.animation.frame.mask

    @mask.setter
    def mask(self, value):
        return

    @property
    def rect(self):
        return self.animation.frame.rect

    @rect.setter
    def rect(self, value):
        return


class DinoState:

    def __init__(self, dino):
        self.dino = dino


class DinoRunning(DinoState):

    def __init__(self, dino):
        super().__init__(dino)
        cells = SPRITE_CELLS['trex']
        self.dino.animation = Animation([ cells['running1'], cells['running2'] ], repeat=8)

    def update(self):
        keys = pg.key.get_pressed()
        if keys[pg.K_DOWN]:
            return DinoCrouch(self.dino)
        elif keys[pg.K_UP]:
            return DinoJump(self.dino)


class DinoCrouch(DinoState):

    def __init__(self, dino):
        super().__init__(dino)
        cells = SPRITE_CELLS['trex']
        self.dino.animation = Animation([ cells['crouch1'], cells['crouch2'] ], repeat=8)
        self.restore = self.dino.rect.copy()
        self.dino.rect = self.dino.animation.images[0].get_rect(bottomleft = self.dino.rect.bottomleft)

    def update(self):
        keys = pg.key.get_pressed()
        if not keys[pg.K_DOWN]:
            self.dino.rect = self.restore
            return DinoRunning(self.dino)
        elif keys[pg.K_UP]:
            self.dino.rect = self.restore
            return DinoJump(self.dino)


class DinoJump(DinoState):

    def __init__(self, dino):
        super().__init__(dino)
        cells = SPRITE_CELLS['trex']
        self.dino.animation = Animation([ cells['jumping1'], cells['jumping2'] ], repeat=8)
        self.y = self.floor = self.dino.rect.bottom
        self.angle = 0
        self.step = 0.07
        self.height = 250

    def update(self):
        self.angle += self.step
        if self.angle >= math.tau / 2:
            self.dino.rect.bottom = self.floor
            return DinoRunning(self.dino)
        self.y = self.floor - math.sin(self.angle) * self.height
        self.dino.rect.bottom = self.y


class Dino(Sprite):

    def __init__(self, *groups, position=None):
        super().__init__(*groups)
        self.state = DinoRunning(self)
        self.image = next(self.animation)
        if position is None:
            position = {}
        self.rect = self.image.get_rect(**position)

    def update(self, dt):
        newstate = self.state.update()
        if newstate:
            self.state = newstate
        self.image = next(self.animation)


class Cloud(Sprite):

    def __init__(self, **spritekwargs):
        spritekwargs.setdefault('image', SPRITE_CELLS['clouds']['cloud'])
        super().__init__(**spritekwargs)


class GameOver(Sprite):

    def __init__(self, centerx, **spritekwargs):
        spritekwargs.setdefault('image', SPRITE_CELLS['text']['gameover'])
        super().__init__(**spritekwargs)
        self.centerx = centerx
        self.vx = 80
        self.ax = -3.0

    def update(self, dt):
        if self.vx < 0 and self.rect.centerx < self.centerx:
            self.vx, self.vy = 0, 0
            self.ax, self.ay = 0, 0
            self.x = self.centerx
        super().update(dt)


class Group(pg.sprite.Group):

    def __init__(self, *sprites):
        super().__init__(*sprites)
        self.enabled = True

    def update(self, dt):
        if self.enabled:
            super().update(dt)


class Ground(Group):

    def __init__(self, *sprites):
        super().__init__(*sprites)

        prev = shared.screen
        for _ in range(32):
            groundtile = GroundTile(bottomleft=prev.rect.bottomleft)
            groundtile.vx = -shared.scrollspeed
            prev = groundtile
            self.add(groundtile)

    def update(self, dt):
        if self.enabled:
            super().update(dt)
            for sprite in self:
                if sprite.rect.right < shared.screen.rect.left:
                    sprite.rect.left = max(sprite.rect.right for sprite in self)
                    sprite.x = sprite.rect.centerx


class Sky(Group):

    def __init__(self, *sprites):
        super().__init__(*sprites)
        self.elapsed = 0
        self.random_delay = random_choice_iter([500,1000,2000,5000])
        self.delay = next(self.random_delay)

    def spawn(self):
        cloud = Cloud(midleft=(shared.screen.rect.right,
                               random.randint(shared.screen.rect.top,
                                              shared.screen.rect.centery-50)))
        cloud.vx = -random.randint(1,10)
        self.add(cloud)

    def update(self, dt):
        if self.enabled:
            super().update(dt)
            self.elapsed += dt
            if self.elapsed >= self.delay:
                self.elapsed %= self.delay
                self.delay = next(self.random_delay)
                self.spawn()


class Enemies(Group):

    def __init__(self, *sprites):
        super().__init__(*sprites)
        self.elapsed = 0
        self.random_delay = random_choice_iter([750, 1000])
        self.delay = next(self.random_delay)

    def spawn(self):
        if not shared.enable_enemies:
            return
        if random.randrange(3) == 0:
            y = shared.floor - SPRITE_CELLS['trex']['running'][0].get_rect().height
            dactyl = Dactyl(midleft=(shared.screen.rect.right, y))
            dactyl.vx = -shared.scrollspeed
            self.add(dactyl)

            dactyl = Dactyl(midbottom=dactyl.rect.midtop)
            dactyl.vx = -shared.scrollspeed
            self.add(dactyl)

            dactyl = Dactyl(midbottom=dactyl.rect.midtop)
            dactyl.vx = -shared.scrollspeed
            self.add(dactyl)

        else:
            c1 = Cactus(bottomleft=(shared.screen.rect.right, shared.floor))
            c2 = Cactus(bottomleft=c1.rect.bottomright)

            c1.vx = -shared.scrollspeed
            c2.vx = -shared.scrollspeed

            self.add(c1, c2)

    def update(self, dt):
        if not self.enabled:
            return
        super().update(dt)

        self.elapsed += dt
        if self.elapsed >= self.delay:
            self.elapsed %= self.delay
            self.delay = next(self.random_delay)
            self.spawn()

        for enemy in self:
            if (enemy.rect.right < shared.screen.rect.left):
                enemy.kill()

        for enemy in self:
            if (enemy.rect.colliderect(shared.dino.rect)
                    and pg.sprite.collide_mask(enemy, shared.dino)):

                gameover = GameOver(shared.screen.rect.centerx, midright=shared.screen.rect.midleft)
                shared.messages.add(gameover)

                dino = shared.dino
                dino.state = 'dead'
                dino.stop()
                dino.update(dt)
                dino.enabled = False

                shared.sky.enabled = False
                shared.ground.enabled = False
                shared.score.enabled = False
                self.enabled = False
                break


def quit():
    pg.event.post(pg.event.Event(pg.QUIT))

def gameplay():
    dt = 0
    running = True

    def draw():
        shared.screen.surface.fill((200,200,200))

        shared.sky.draw(shared.screen.surface)
        shared.ground.draw(shared.screen.surface)
        shared.enemies.draw(shared.screen.surface)
        shared.screen.surface.blit(shared.dino.image, shared.dino.rect)
        shared.messages.draw(shared.screen.surface)
        shared.score.draw(shared.screen.surface)

    def update():
        shared.messages.update(dt)
        shared.dino.update(dt)
        shared.ground.update(dt)
        shared.sky.update(dt)
        shared.enemies.update(dt)
        shared.score.update(dt)

    while running:
        dt = clock.tick(FRAMERATE)
        for event in pg.event.get():
            if event.type == pg.QUIT:
                running = False
            elif event.type == pg.KEYDOWN:
                if event.key in (pg.K_q, pg.K_ESCAPE):
                    quit()
                elif not shared.dino.enabled and event.key == pg.K_r:
                    restart()

        if (shared.logo.alive() and
                shared.logo.rect.right < shared.screen.rect.left):
            shared.logo.kill()

        pressed = pg.key.get_pressed()

        if shared.dino.enabled:
            if pressed[pg.K_UP]:
                shared.dino.jump()
            elif pressed[pg.K_DOWN]:
                shared.dino.crouch()
            else:
                shared.dino.stand()

        update()
        draw()
        pg.display.flip()

class Clock:

    def __init__(self, framerate):
        self.framerate = framerate
        self._clock = pg.time.Clock()

    def tick(self):
        return self._clock.tick(self.framerate)


class Screen:

    def __init__(self, size):
        self.surface = pg.display.set_mode(size)
        self.background = self.surface.copy()
        self.rect = self.surface.get_rect()

    def clear(self):
        self.surface.blit(self.background, (0, 0))


class Scene:

    def __init__(self, engine):
        self.engine = engine
        self.eventdispatch = {}

    def draw(self, surface):
        pass

    def enter(self):
        pass

    def exit(self):
        pass

    def update(self, dt):
        pass


class TestScene(Scene):

    def enter(self):
        print('enter')
        self.elapsed = 0

    def update(self, dt):
        self.elapsed += dt
        if self.elapsed > 1000:
            pg.event.post(pg.event.Event(SCENE_EVENT, method='pop', args=tuple()))


def rendertext(s, size, color):
    font = pg.font.Font(None, size)
    image = font.render(s, True, color)
    return image

class MainMenu(Scene):

    def __init__(self, engine):
        super().__init__(engine)
        self.sprites = pg.sprite.Group()
        size = 130
        color = (13, 35, 52)
        sprite1 = ImageSprite(rendertext('TREX-RUSH', size, color),
                self.sprites,
                position=dict(center=self.engine.screen.rect.center))
        sprite2 = ImageSprite(rendertext('PRESS ENTER START', size, color),
                self.sprites,
                position=dict(midtop=sprite1.rect.midbottom))
        self.eventdispatch[pg.KEYDOWN] = self.on_keydown

    def draw(self, surface):
        self.sprites.draw(surface)

    def on_keydown(self, event):
        if event.key == pg.K_ESCAPE:
            pg.event.post(pg.event.Event(pg.QUIT))
        elif event.key == pg.K_RETURN:
            self.engine.scene = Gameplay(self.engine)

    def update(self, dt):
        self.sprites.update(dt)


class Gameplay(Scene):

    def __init__(self, engine):
        super().__init__(engine)
        self.eventdispatch[pg.KEYDOWN] = self.on_keydown
        self.sprites = pg.sprite.Group()
        self.dino = Dino(position=dict(bottomleft=(200, 350)))
        self.floor = self.dino.rect.bottom
        self.sprites.add(self.dino)
        x = 0
        tiles = tuple(SPRITE_CELLS['ground'].values())
        n = self.engine.screen.rect.width // SPRITE_CELLS['ground']['hump1'].get_width()
        for _ in range(n * 2):
            sprite = GroundTile(random.choice(tiles), position=dict(x=x, top=self.floor))
            self.sprites.add(sprite)
            x += sprite.rect.width
        self.spawn = 0
        self.reset_spawn()

    def reset_spawn(self):
        self.spawn = random.choice([60, 75, 90, 120])

    def draw(self, surface):
        self.sprites.draw(surface)

    def draw_rects(self):
        for sprite in self.sprites:
            pg.draw.rect(surface, (200, 0, 0), sprite.rect, 2)

    def on_keydown(self, event):
        if event.key == pg.K_ESCAPE:
            pg.event.post(pg.event.Event(pg.QUIT))
            self.engine.scene = MainMenu(self.engine)

    def update(self, dt):
        self.sprites.update(dt)
        groundtiles = tuple(sprite for sprite in self.sprites if isinstance(sprite, GroundTile))
        right = max(tile.rect.right for tile in groundtiles)
        for tile in groundtiles:
            if tile.rect.right < self.engine.screen.rect.left:
                tile.rect.left = right
                tile.x = tile.rect.x
        self.spawn -= 1
        if self.spawn == 0:
            class_ = random.choice(EnemyClasses)
            position = dict(left = self.engine.screen.rect.right, bottom = self.floor)
            self.sprites.add(class_(position=position))
            self.reset_spawn()


class Engine:

    def __init__(self, clock, screen):
        self.clock = clock
        self.screen = screen
        #: external interface to change scene
        self.scene = None
        #: the real, current scene
        self._scene = None

    def run(self, scene):
        self._scene = self.scene = scene
        while not pg.event.peek(pg.QUIT):
            self.step()

    def step(self):
        dt = self.clock.tick()
        for event in pg.event.get():
            if event.type in self._scene.eventdispatch:
                self._scene.eventdispatch[event.type](event)
        self._scene.update(dt)
        self.screen.clear()
        self._scene.draw(self.screen.surface)
        pg.display.flip()
        if self.scene is not self._scene:
            self._scene.exit()
            self._scene = self.scene
            self._scene.enter()


def main(argv=None):
    """
    T-Rex Rush in Pygame.
    """
    def sizetype(s):
        return tuple(map(int, s.split(',')))

    parser = argparse.ArgumentParser(prog=Path(__file__).stem, description=main.__doc__)
    parser.add_argument('--debug', action='store_true', help='Debug logging [%(default)s].')
    parser.add_argument('--framerate', type=int, default=FRAMERATE, help='Framerate [%(default)s].')
    parser.add_argument('--screen', type=sizetype, default=SCREEN_SIZE, help='Screen size [%(default)s].')
    args = parser.parse_args(argv)

    if args.debug:
        logging.basicConfig(level=logging.DEBUG)

    pg.mixer.pre_init(44100, -16, 2, 2048)
    npass, nfail = pg.init()
    init()

    clock = Clock(args.framerate)
    screen = Screen(args.screen)
    screen.background.fill((200,200,200))
    engine = Engine(clock, screen)

    scene = MainMenu(engine)
    scene = Gameplay(engine)
    engine.run(scene)

if __name__ == '__main__':
    main()
