import logging
import math
import os
import random

from itertools import cycle

import pygame as pg

pg.mixer.pre_init(44100, -16, 2, 2048)
pg.init()

clock = pg.time.Clock()

font = pg.font.Font(None, 128)

FRAMERATE = 60
SPRITE_SHEET = pg.image.load('images/sprites.png')

def cell(x,y,w,h):
    return SPRITE_SHEET.subsurface(pg.Rect(x,y,w,h))

def random_choice_iter(possible):
    while True:
        yield random.choice(possible)

SHEET_TREX = {
    'idle': [cell(1338,2,88,94)],
    'blink': [cell(1426,2,88,94)],
    'dead': [cell(1684,147,88,94)],
    'running': [cell(1514,2,88,94), cell(1602,2,88,94)],
    'crouch': [cell(1866,36,118,60), cell(1984,36,118,60)],
    'jumping': [cell(2113,2,88,77)],
}

SHEET_GROUND = {
    'hump1': cell(1459,104,33,26),
    'dip1': cell(1518,104,33,26),
    'hump2': cell(2101,104,33,26),
    'hump3': cell(2148,104,33,26),
    'straight1': cell(2,104,33,26),
    'straight2': cell(34,104,33,26),
}

SHEET_CACTI = {
    'cactus1': cell(446,2,34,70),
    'cactus2': cell(514,2,34,70),
    'cactus3': cell(548,2,34,70),
    'cactus4': cell(582,2,34,70),
    'cactus5': cell(616,2,34,70),
    'bigcactus1': cell(652,2,50,100),
    'bigcactus2': cell(702,2,48,100),
    'bigcactus3': cell(752,2,50,100),
}

SHEET_CLOUDS = {
    'cloud': cell(166,2,92,27),
}

SHEET_DACTYL = {
    'dactyl': [cell(260,14,92,68), cell(352,2,92,60)]
}

SHEET_TEXT = {
    'gameover': cell(2225,10,225,58),
    'logo': cell(2217,72,230,31),
    '0': cell(28,147,68,88),
    '1': cell(95,147,43,88),
    '2': cell(138,147,71,88),
    '3': cell(208,147,68,88),
    '4': cell(275,147,68,88),
    '5': cell(343,147,71,88),
    '6': cell(413,147,68,88),
    '7': cell(480,147,68,88),
    '8': cell(548,147,68,88),
    '9': cell(616,147,68,88),
}

jump_sound = pg.mixer.Sound('sounds/jump.wav')

class shared(object):

    enable_enemies = True
    shown_banner = False


class Animation(object):

    def __init__(self, images, delay=100):
        self.image_iterator = cycle(images)
        self.image = next(self.image_iterator)
        self.rect = self.image.get_rect()
        self.delay = delay
        self.elapsed = 0

    def update(self, dt):
        self.elapsed += dt
        if self.elapsed >= self.delay:
            self.elapsed = self.elapsed % self.delay
            self.image = next(self.image_iterator)
            self.rect = self.image.get_rect()


def quit():
    pg.event.post(pg.event.Event(pg.QUIT))

def Surface(size):
    return pg.Surface(size, pg.SRCALPHA)

class ImageObject(object):

    def __init__(self, surface):
        self.surface = surface
        self.rect = self.surface.get_rect()


class Sprite(pg.sprite.Sprite):

    def __init__(self, **kwargs):
        super(Sprite, self).__init__()

        assert 'image' in kwargs or 'size' in kwargs

        if 'image' in kwargs:
            image = kwargs['image']
        else:
            image = Surface(kwargs['size'])
        self.image = image

        if 'fill' in kwargs:
            self.image.fill(kwargs['fill'])

        self.rect = self.image.get_rect()

        self.mask = pg.mask.from_surface(self.image)

        for name,value in kwargs.items():
            if hasattr(self.rect, name):
                setattr(self.rect, name, value)

        self.alignattr = 'midbottom'

        self.x, self.y = getattr(self.rect, self.alignattr)
        self.vx, self.vy = 0, 0
        self.ax, self.ay = 0, 0
        self.jumping = False

        self.logger = logging.getLogger('trex')

    def jump(self):
        if not self.jumping:
            self.ay = -1.56
            self.jumping = True
            jump_sound.play()

    def land(self):
        self.logger.debug('land')
        self.jumping = False
        self.ax, self.ay = 0, 0
        self.vx, self.vy = 0, 0

    def update(self, dt):
        # gravity
        if self.jumping:
            self.ay += .115

        self.x += self.vx
        self.y += self.vy

        self.vx += self.ax
        self.vy += self.ay

        setattr(self.rect, self.alignattr, (self.x, self.y))


class Cloud(Sprite):

    def __init__(self, **spritekwargs):
        spritekwargs.setdefault('image', SHEET_CLOUDS['cloud'])
        super(Cloud, self).__init__(**spritekwargs)


class Text(Sprite):

    def __init__(self, text, **spritekwargs):

        images = [font.render(line, True, (255,255,255)) for line in text.splitlines()]
        rects = [image.get_rect() for image in images]

        bigrect = pg.Rect(0,0,max(rect.width for rect in rects),sum(rect.height for rect in rects))

        bigimage = Surface(bigrect.size)

        y = 0
        for image, rect in zip(images, rects):
            bigimage.blit(image, (0, y))
            y += rect.height

        super(Text, self).__init__(image=bigimage, **spritekwargs)


class Logo(Sprite):

    def __init__(self, centerx, **spritekwargs):
        spritekwargs.setdefault('image', SHEET_TEXT['logo'])
        super(Logo, self).__init__(**spritekwargs)
        self.centerx = centerx
        self.vx = 80
        self.ax = -3.0
        self.state = 'slideon'
        self.elapsed = 0

    def update(self, dt):
        if self.state == 'slideon':
            if self.vx < 0 and self.rect.centerx < self.centerx:
                self.vx, self.vy = 0, 0
                self.ax, self.ay = 0, 0
                self.x = self.centerx
                self.state = 'idle'
        elif self.state == 'idle':
            self.elapsed += dt
            if self.elapsed > 1000:
                self.state = 'slideoff'
                self.vx = 40
                self.ax = -3.0
        elif self.state == 'slideoff':
            if self.rect.right < shared.screen.rect.left:
                self.kill()
        super(Logo, self).update(dt)


class Score(Sprite):

    def __init__(self, **spritekwargs):
        self.value = 0
        spritekwargs.setdefault('image', Surface((0,0)))
        super(Score, self).__init__(**spritekwargs)

        widest = max(SHEET_TEXT[c].get_rect().width for c in '0123456789')
        self.rect = pg.Rect(0,0,widest*4,100)
        self.rect.topright = shared.screen.rect.topright

        self.elapsed = 0
        self.delay = 1000

    @property
    def image(self):
        s = '%04d' % self.value
        images = [SHEET_TEXT[c] for c in s]
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

        return surface

    @image.setter
    def image(self, value):
        return

    def update(self, dt):
        self.elapsed += dt
        if self.elapsed >= self.delay:
            self.value += 1
            self.elapsed %= self.delay


class Dino(Sprite):

    def __init__(self, **kwargs):
        self.animations = { state:Animation(SHEET_TREX[state])
                            for state in ['running', 'crouch', 'jumping', 'dead']}
        self.state = 'running'
        super(Dino, self).__init__(image=Surface((0,0)), **kwargs)

    def crouch(self):
        if not self.jumping:
            self.state = 'crouch'

    @property
    def animation(self):
        return self.animations[self.state]

    @property
    def image(self):
        return self.animation.image

    @image.setter
    def image(self, value):
        return

    def land(self):
        super(Dino, self).land()
        self.state = 'running'
        self.rect.bottom = shared.floor
        self.x, self.y = getattr(self.rect, self.alignattr)

    def stand(self):
        if self.state != 'jumping':
            self.land()

    @property
    def rect(self):
        return self.animation.rect

    @rect.setter
    def rect(self, value):
        return

    def jump(self):
        if not self.jumping:
            super(Dino, self).jump()
            r = self.rect.copy()
            self.state = 'jumping'
            self.rect.midtop = r.midtop
            self.x, self.y = getattr(self.rect, self.alignattr)

    def update(self, dt):
        self.animation.update(dt)
        super(Dino, self).update(dt)


class GroundTile(Sprite):

    def __init__(self, **spritekwargs):
        spritekwargs.setdefault('image', random.choice(list(SHEET_GROUND.values())))
        super(GroundTile, self).__init__(**spritekwargs)


class Cactus(Sprite):

    def __init__(self, **spritekwargs):
        spritekwargs.setdefault('image', random.choice(list(SHEET_CACTI.values())))
        super(Cactus, self).__init__(**spritekwargs)


class Dactyl(Sprite):

    def __init__(self, **spritekwargs):
        self.animation = Animation(SHEET_DACTYL['dactyl'])
        super(Dactyl, self).__init__(image=Surface((0,0)), **spritekwargs)

    @property
    def image(self):
        return self.animation.image

    @image.setter
    def image(self, value):
        return

    def update(self, dt):
        self.animation.update(dt)
        super(Dactyl, self).update(dt)


class Cloud(Sprite):

    def __init__(self, **spritekwargs):
        spritekwargs.setdefault('image', SHEET_CLOUDS['cloud'])
        super(Cloud, self).__init__(**spritekwargs)


class GameOver(Sprite):

    def __init__(self, centerx, **spritekwargs):
        spritekwargs.setdefault('image', SHEET_TEXT['gameover'])
        super(GameOver, self).__init__(**spritekwargs)
        self.centerx = centerx
        self.vx = 80
        self.ax = -3.0

    def update(self, dt):
        if self.vx < 0 and self.rect.centerx < self.centerx:
            self.vx, self.vy = 0, 0
            self.ax, self.ay = 0, 0
            self.x = self.centerx
        super(GameOver, self).update(dt)


class Group(pg.sprite.Group):

    def __init__(self, *sprites):
        super(Group, self).__init__(*sprites)
        self.enabled = True


class Ground(Group):

    def __init__(self, *sprites):
        super(Ground, self).__init__(*sprites)

        prev = shared.screen
        for _ in range(48):
            groundtile = GroundTile(bottomleft=prev.rect.bottomleft)
            groundtile.vx = -shared.scrollspeed
            prev = groundtile
            self.add(groundtile)

    def update(self, dt):
        super(Ground, self).update(dt)
        for sprite in self:
            if sprite.rect.right < shared.screen.rect.left:
                sprite.rect.left = max(sprite.rect.right for sprite in self)
                sprite.x = sprite.rect.centerx


class Sky(Group):

    def __init__(self, *sprites):
        super(Sky, self).__init__(*sprites)
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
        super(Sky, self).update(dt)
        self.elapsed += dt
        if self.elapsed >= self.delay:
            self.elapsed %= self.delay
            self.delay = next(self.random_delay)
            self.spawn()


class Enemies(Group):

    def __init__(self, *sprites):
        super(Enemies, self).__init__(*sprites)
        self.elapsed = 0
        self.random_delay = random_choice_iter([750, 1000])
        self.delay = next(self.random_delay)

    def spawn(self):
        if not shared.enable_enemies:
            return
        if random.randrange(3) == 0:
            y = shared.floor - SHEET_TREX['running'][0].get_rect().height
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
        super(Enemies, self).update(dt)

        self.elapsed += dt
        if self.elapsed >= self.delay:
            self.elapsed %= self.delay
            self.delay = next(self.random_delay)
            self.spawn()

        for sprite in self:
            if sprite.rect.right < shared.screen.rect.left - 25:
                sprite.kill()
            elif (sprite.rect.colliderect(shared.dino.rect)
                    and pg.sprite.collide_mask(sprite, shared.dino)):

                gameover = GameOver(shared.screen.rect.centerx, midright=shared.screen.rect.midleft)
                shared.messages.add(gameover)

                shared.dino.state = 'dead'
                shared.dinomanager.enabled = False
                shared.sky.enabled = False
                shared.ground.enabled = False
                shared.score.enabled = False
                self.enabled = False
                break


class DinoManager(Group):

    def update(self, dt):
        super(DinoManager, self).update(dt)

        if shared.dino.rect.bottom > shared.floor:
            shared.dino.land()


def gameplay():
    dt = 0
    state = 'playing'
    running = True
    while running:
        for event in pg.event.get():
            if event.type == pg.QUIT:
                running = False
            elif event.type == pg.KEYDOWN:
                if event.key in (pg.K_q, pg.K_ESCAPE):
                    quit()
                elif state == 'gameover' and event.key == pg.K_r:
                    restart()

        pressed = pg.key.get_pressed()

        if shared.logo.alive() and shared.logo.rect.right < shared.screen.rect.left:
            shared.logo.kill()

        if shared.dinomanager.enabled:
            if pressed[pg.K_UP]:
                shared.dino.jump()
            elif pressed[pg.K_DOWN]:
                shared.dino.crouch()
            else:
                shared.dino.stand()

        shared.messages.update(dt)

        shared.dinomanager.update(dt)

        if shared.ground.enabled:
            shared.ground.update(dt)

        if shared.sky.enabled:
            shared.sky.update(dt)

        if shared.enemies.enabled:
            shared.enemies.update(dt)

        if shared.score.enabled:
            shared.score.update(dt)

        state = 'playing' if shared.dinomanager.enabled else 'gameover'

        shared.screen.surface.fill((200,200,200))

        shared.sky.draw(shared.screen.surface)
        shared.ground.draw(shared.screen.surface)
        shared.enemies.draw(shared.screen.surface)
        shared.dinomanager.draw(shared.screen.surface)
        shared.messages.draw(shared.screen.surface)

        shared.score.draw(shared.screen.surface)

        pg.display.flip()

        dt = clock.tick(FRAMERATE)

def restart():
    shared.screen = ImageObject(pg.display.get_surface())

    shared.scrollspeed = 10

    shared.messages = Group()

    if not shared.shown_banner:
        shared.logo = Logo(shared.screen.rect.centerx, midright=shared.screen.rect.midleft)
        shared.messages.add(shared.logo)
        shared.shown_banner = True

    shared.score = Group(Score(topright=shared.screen.rect.move(-25,25).topright))

    shared.dino = Dino(bottomleft=shared.screen.rect.move(100, -12).bottomleft)
    shared.dinomanager = DinoManager(shared.dino)
    shared.floor = shared.dino.rect.bottom

    shared.enemies = Enemies()
    shared.sky = Sky()

    shared.ground = Ground()

    shared.logger = logging.getLogger()

    gameplay()

def main():
    """
    T-Rex Rush in Pygame.
    """
    import argparse

    def sizetype(s):
        return tuple(map(int, s.strip('()').split(',')))

    parser = argparse.ArgumentParser(description=main.__doc__)
    parser.add_argument('--debug', action='store_true', help='Debug logging. [%(default)s].')
    parser.add_argument('--screen', type=sizetype, default=(1024,400), help='Screen size. [%(default)s].')
    parser.add_argument('--disable-enemies', action='store_true', help='Don\'t generate enemies. [%(default)s].')
    args = parser.parse_args()

    if args.debug:
        logging.basicConfig(level=logging.DEBUG)

    if args.disable_enemies:
        shared.enable_enemies = False

    pg.display.set_mode(args.screen)

    restart()

if __name__ == '__main__':
    main()
