#import built-in
import tkinter as tk
from tkinter import ttk
from PIL import ImageTk, Image
import csv
import os
import time
import threading
from datetime import datetime
import re

#Library
import pyautogui
import linux_window as gw
import cv2
import numpy as np
from PIL import ImageGrab
import random
from Xlib import display as _xdisplay, X as _X
from Xlib.ext import xtest as _xtest

_scroll_display = _xdisplay.Display()

def _wheelScroll(x, y, ticks):
    """pyautogui.scroll() doesn't register on this Xephyr/Wine setup; raw
    XTest button4/5 (scroll up/down) does, so this bypasses pyautogui for
    wheel scrolling specifically."""
    button = 4 if ticks > 0 else 5
    _xtest.fake_input(_scroll_display, _X.MotionNotify, x=int(x), y=int(y))
    _scroll_display.sync()
    for _ in range(abs(ticks)):
        _xtest.fake_input(_scroll_display, _X.ButtonPress, button)
        _scroll_display.sync()
        _xtest.fake_input(_scroll_display, _X.ButtonRelease, button)
        _scroll_display.sync()
        time.sleep(0.05)

class ShopItem:
    def __init__(self, path='', image=None, price=0, count=0):
        self.path=path
        self.image=image
        self.price=price
        self.count=count

    def __repr__(self):
        return f'ShopItem(path={self.path}, image={self.image}, price={self.price}, count={self.count})'

class RefreshStatistic:
    def __init__(self):
        self.refresh_count = 0
        self.items = {}
        self.start_time = datetime.now()
        
    def updateTime(self):
        self.start_time = datetime.now()

    def addShopItem(self, path: str, name='', price=0, count=0):
        #load image using cv2, need to convert from BGR to RGB
        image = cv2.imread(os.path.join('assets', path))
        image = cv2.cvtColor(image, cv2.COLOR_BGR2RGB)
        newItem = ShopItem(path, image, price, count)
        self.items[name] = newItem
    
    def getInventory(self):
        return self.items

    def getName(self):
        return list(self.items.keys())

    def getPath(self):
        return [shop_item.path for shop_item in self.items.values()]
    
    def getItemCount(self):
        return [shop_item.count for shop_item in self.items.values()]
    
    def getTotalCost(self):
        total = 0
        for shop_item in self.items.values():
            total += shop_item.price * shop_item.count
        return total
    
    def incrementRefreshCount(self):
        self.refresh_count += 1
    
    def writeToCSV(self):
        res_folder = 'ShopRefreshHistory'
        if not os.path.exists(res_folder):
            os.makedirs(res_folder)

        gen_path = 'refreshAttempt'
        for name in self.getName():
            gen_path += name[:4]
        gen_path += '.csv'

        path = os.path.join(res_folder, gen_path)

        if not os.path.isfile(path):
            with open(path, 'w', newline='') as file:
                writer = csv.writer(file)
                column_name = ['Time', 'Duration', 'Refresh count', 'Skystone spent', 'Gold spent']
                column_name.extend(self.getName())
                writer.writerow(column_name)
        with open(path, 'a', newline='') as file:
            writer = csv.writer(file)
            data = [self.start_time, datetime.now()-self.start_time, self.refresh_count, self.refresh_count*3, self.getTotalCost()]
            data.extend(self.getItemCount())
            writer.writerow(data)

class SecretShopRefresh:
    def __init__(self, title_name: str, callback = None, tk_instance: tk = None, budget: int = None, allow_move: bool = False, debug: bool = False, join_thread: bool = False):
        #init state
        self.debug = debug
        self.loop_active = False
        self.loop_finish = True
        self.mouse_sleep = 0.3
        self.screenshot_sleep = 0.3
        self.callback = callback if callback else self.refreshFinishCallback
        self.budget = budget
        self.allow_move = allow_move
        self.join_thread = join_thread

        self.loading_asset = cv2.imread(os.path.join('assets', 'loading.jpg'))
        self.loading_asset= cv2.cvtColor(self.loading_asset, cv2.COLOR_BGR2GRAY)

        #find window
        self.title_name = title_name
        windows = gw.getWindowsWithTitle(self.title_name)
        self.window = next((w for w in windows if w.title == self.title_name), None)

        self.tk_instance = tk_instance
        self.rs_instance = RefreshStatistic()

    #Start shop refresh macro
    def start(self):
        if self.loop_active or not self.loop_finish:
            return

        self.loop_active = True
        self.loop_finish = False
        refresh_thread = threading.Thread(target=self.shopRefreshLoop)
        refresh_thread.daemon = True
        refresh_thread.start()
        if self.join_thread:
            try:
                refresh_thread.join()
            except KeyboardInterrupt:
                print('Terminating shop refresh ...')
                self.loop_active = False
                refresh_thread.join()

    def refreshFinishCallback(self):
        print('Terminated!')

    def shopRefreshLoop(self):
        
        try:
            if self.window.isMaximized or self.window.isMinimized:
                self.window.restore()
            if not self.allow_move: self.window.moveTo(0, 0)
            self.window.resizeTo(906, 539)
        except Exception as e:
            print(e)
            self.loop_active = False
            self.loop_finish = True
            self.callback()
            return

        #show mini display
        #generating mini image
        mini_images = []
        hint, mini_labels = None, None
        if self.tk_instance:
            selected_path = self.rs_instance.getPath()
            for path in selected_path:
                img = Image.open(os.path.join('assets', path))
                img = img.resize((45,45))
                img = ImageTk.PhotoImage(img)
                mini_images.append(img)
            hint, mini_labels = self.showMiniDisplays(mini_images)

        #update state on minidisplay
        def updateMiniDisplay():
            for label, count in zip(mini_labels, self.rs_instance.getItemCount()):
                label.config(text=count)
            
        time.sleep(self.mouse_sleep)
        
        if not self.loop_active:
            if hint: hint.destroy()
            self.loop_finish = True
            self.callback()
            return
        
        try:
            #replace with window activate in python
            # window.minimize()
            # window.maximize()
            # window.restore()
            try:
                self.window.activate()
            except Exception as e:
                print(e)
            
            self.rs_instance.updateTime()
            self.clickShop()
            time.sleep(1)
            
            #item sliding const
            sliding_time = max(0.7+self.screenshot_sleep, 1)

            #Loop through shop 
            while self.loop_active:
                
                self.window.resizeTo(906, 539)
                
                # screenshot = self.takeScreenshot()
                # ss = cv2.cvtColor(screenshot, cv2.COLOR_BGR2RGB)
                # cv2.imwrite('screenshot.png',ss)
                # input('wait')

                #array for determining if an item has been purchsed in this loop
                brought = set()
                if not self.loop_active: break

                #take screenshot, check for items, buy all items that appear
                time.sleep(sliding_time)    #This is a constant sleep to account for the item sliding in frame
                
                ###start of bundle refresh
                screenshot = self.takeScreenshot()
                #process_screenshot = cv2.cvtColor(screenshot, cv2.COLOR_BGR2GRAY)
                process_screenshot = screenshot

                #show processed image
                # cv2.imshow('Press any key to continue ...', process_screenshot)
                # cv2.waitKey(0)
                # cv2.destroyAllWindows()
                    
                # #checks if loading screen is blocking - No longer works cause loading symbol changed
                # check_screen, reset = self.checkLoading(process_screenshot)
                # if check_screen is None:
                #     break      
                # else:
                #     process_screenshot = check_screen

                # if reset:
                #     self.scrollUp()
                #     time.sleep(0.5)
                #     continue
                
                #loop through all the assets to find item to buy
                for key, shop_item in self.rs_instance.getInventory().items():
                    pos = self.findItemPosition(process_screenshot, shop_item.image)
                    if pos is not None:
                        self.clickBuy(pos)
                        shop_item.count += 1
                        brought.add(key)

                #real time count UI update
                if hint: updateMiniDisplay()
                if not self.loop_active: break
                
                #scroll shop
                self.scrollShop()
                time.sleep(max(0.3, self.screenshot_sleep))
                if not self.loop_active: break

                ###start of bundle refresh
                screenshot = self.takeScreenshot()
                #process_screenshot = cv2.cvtColor(screenshot, cv2.COLOR_BGR2GRAY)
                process_screenshot = screenshot

                #show processed image
                # cv2.imshow('Press any key to continue ...', process_screenshot)
                # cv2.waitKey(0)
                # cv2.destroyAllWindows()

                # #checks if loading screen is blocking  - no longer works cause loading changed
                # check_screen, reset = self.checkLoading(process_screenshot)
                # if check_screen is None:
                #     break      
                # else:
                #     process_screenshot = check_screen

                # if reset:
                #     for key in brought:
                #         value = self.rs_instance.getInventory().get(key)
                #         if value:
                #             value.count -= 1
                #     self.scrollUp()
                #     time.sleep(0.5)
                #     continue
                
                #loop through all the assets to find item to buy
                for key, shop_item in self.rs_instance.getInventory().items():
                    if key in brought:
                        continue
                    pos = self.findItemPosition(process_screenshot, shop_item.image)
                    if pos is not None:
                        self.clickBuy(pos)
                        shop_item.count += 1

                if hint: updateMiniDisplay()
                if not self.loop_active: break
                
                #check budget
                if self.budget:
                    if self.rs_instance.refresh_count >= self.budget // 3:
                        break
                    
                #refresh shop
                self.clickRefresh()
                self.rs_instance.incrementRefreshCount()
                time.sleep(self.mouse_sleep)
                if self.window.title != self.title_name: break

        except Exception as e:
            print(e)
            if hint: hint.destroy()
            self.rs_instance.writeToCSV()
            self.loop_active = False
            self.loop_finish = True
            self.callback()
            return
            
        if hint: hint.destroy()
        self.rs_instance.writeToCSV()
        self.loop_active = False
        self.loop_finish = True
        self.callback()

    #show mini display
    def showMiniDisplays(self, mini_images):
        bg_color = '#171717'
        fg_color = '#dddddd'

        if self.tk_instance is None:
            return None, None
        #Display exit key
        hint = tk.Toplevel(self.tk_instance)
        hint.geometry(r'200x200+%d+%d' % (self.window.left, self.window.top+self.window.height))
        hint.title('Hint')
        hint.iconbitmap(os.path.join('assets','icon.ico'))
        tk.Label(master=hint, text='Press ESC to stop refreshing!', bg=bg_color, fg=fg_color).pack()
        hint.config(bg=bg_color)

        #Display stat
        mini_stats = tk.Frame(master=hint, bg=bg_color)
        mini_labels = []
        
        #packing mini image
        for img in mini_images:
            frame = tk.Frame(mini_stats, bg=bg_color)
            tk.Label(master=frame, image=img, bg=bg_color).pack(side=tk.LEFT)
            count = tk.Label(master=frame, text='0', bg=bg_color, fg='#FFBF00')
            count.pack(side=tk.RIGHT)
            mini_labels.append(count)
            frame.pack()
        mini_stats.pack()
        return hint, mini_labels

    #add item to list
    def addShopItem(self, path: str, name='', price=0, count=0):
        self.rs_instance.addShopItem(path, name, price, count)

    #take screenshot of entire window
    def takeScreenshot(self):
        try:
            #replace with window activate in python
            # window.minimize()
            # window.maximize()
            # window.restore()
            try:
                self.window.activate()
            except Exception as e:
                print(e)

            #fix pyautogui's multiscreen bug
            #screenshot = pyautogui.screenshot(region=(self.window.left, self.window.top, self.window.width, self.window.height))
            region=[self.window.left, self.window.top, self.window.width, self.window.height]
            screenshot = ImageGrab.grab(bbox=(region[0], region[1], region[2] + region[0], region[3] + region[1]), all_screens=True)
            screenshot = np.array(screenshot)
            return screenshot
        
        except Exception as e:
            print(e)
            return None
        
    def checkLoading(self, process_screenshot):
        result = cv2.matchTemplate(process_screenshot, self.loading_asset, cv2.TM_CCOEFF_NORMED)
        loc = np.where(result >= 0.75)
        if loc[0].size <= 0:
            return process_screenshot, False
        
        for _ in range(14):
            time.sleep(1)
            screenshot = self.takeScreenshot()
            process_screenshot = cv2.cvtColor(screenshot, cv2.COLOR_BGR2GRAY)
            result = cv2.matchTemplate(process_screenshot, self.loading_asset, cv2.TM_CCOEFF_NORMED)
            loc = np.where(result >= 0.75)
            if loc[0].size <= 0:
                time.sleep(1.5)
                screenshot = self.takeScreenshot()
                process_screenshot = cv2.cvtColor(screenshot, cv2.COLOR_BGR2GRAY)
                return process_screenshot, True

        return None, False

    #return item position
    def findItemPosition(self, process_screenshot, process_item):
        #reduce noise
        # process_screenshot = cv2.GaussianBlur(process_screenshot, (3, 3), 0)
        # process_item = cv2.GaussianBlur(process_item, (3, 3), 0)

        result = cv2.matchTemplate(process_screenshot, process_item, cv2.TM_CCOEFF_NORMED)
        loc = np.where(result >= 0.70)
        x, y = 1, 1
        #print(len(loc[0]))

        #debug mode!
        if self.debug and loc[0].size > 0:
            print('Number of template found: ' + loc[0].size)
            debug_screenshot = process_screenshot.copy()
            #debug_screenshot = cv2.cvtColor(debug_screenshot, cv2.COLOR_GRAY2RGB)
            
            #create heatmap
            result_norm = cv2.normalize(result, None, 0, 1, cv2.NORM_MINMAX)
            result_uint8 = np.uint8(result_norm * 255)
            heatmap = cv2.applyColorMap(result_uint8, cv2.COLORMAP_JET)

            #show all on screen
            for pt in zip (*loc[::-1]):
                cv2.rectangle(debug_screenshot, pt, (pt[0] + process_item.shape[1], pt[1] + process_item.shape[0]), (0, 255, 0), 1)
            
            cv2.imshow('Press any key to continue ...', debug_screenshot)
            cv2.imshow('Heatmap', heatmap)
            #cv2.imwrite('Debug.png', debug_screenshot)
            cv2.waitKey(0)
            cv2.destroyAllWindows()
            time.sleep(1)
            self.window.activate()
            time.sleep(1)
        
        if loc[0].size > 0:
            x = self.window.left + self.window.width*0.90
            y = self.window.top + loc[0][0] + self.window.height*0.085
            pos = (x, y)
            return pos
        return None
    
    #BUY MACRO
    def clickBuy(self, pos):
        if pos is None:
            return False
        x, y = pos
        pyautogui.moveTo(x, y)
        time.sleep(0.15)
        pyautogui.click(clicks=2, interval=self.mouse_sleep)
        time.sleep(self.mouse_sleep)
        self.clickConfirmBuy()
        return True

    def clickConfirmBuy(self):
        x = self.window.left + self.window.width * 0.586
        y = self.window.top + self.window.height * 0.706
        pyautogui.moveTo(x, y)
        time.sleep(0.15)
        pyautogui.click(clicks=2, interval=self.mouse_sleep)
        time.sleep(self.mouse_sleep)
        time.sleep(self.screenshot_sleep)   #Account for Loading

        # #checks if loading screen is blocking
        # screenshot = self.takeScreenshot()
        # process_screenshot = cv2.cvtColor(screenshot, cv2.COLOR_BGR2GRAY)
        # self.checkLoading(process_screenshot)

    #REFRESH MACRO
    def clickRefresh(self):
        x = self.window.left + self.window.width * 0.169
        y = self.window.top + self.window.height * 0.918
        pyautogui.moveTo(x, y)
        time.sleep(0.15)
        pyautogui.click(clicks=2, interval=self.mouse_sleep)
        time.sleep(self.mouse_sleep)
        self.clickConfirmRefresh()

    def clickConfirmRefresh(self):
        x = self.window.left + self.window.width * 0.584
        y = self.window.top + self.window.height * 0.639
        pyautogui.moveTo(x, y)
        time.sleep(0.15)
        pyautogui.click(clicks=2, interval=self.mouse_sleep)
        time.sleep(self.screenshot_sleep)   #Account for Loading

    #SHOP MACRO
    def clickShop(self):
        #wake window
        x = self.window.left + self.window.width * 0.05
        y = self.window.top + self.window.height * 0.41
        pyautogui.moveTo(x, y)
        time.sleep(0.15)
        pyautogui.click()

        time.sleep(self.mouse_sleep)

        #old lobby
        x = self.window.left + self.window.width * 0.44
        y = self.window.top + self.window.height * 0.26
        pyautogui.moveTo(x, y)
        time.sleep(0.15)
        pyautogui.click()

        time.sleep(self.mouse_sleep)

        #new lobby
        x = self.window.left + self.window.width * 0.05
        y = self.window.top + self.window.height * 0.41
        pyautogui.moveTo(x, y)
        time.sleep(0.15)
        pyautogui.click()

    def scrollShop(self):
        x = self.window.left + self.window.width * 0.58
        y = self.window.top + self.window.height * 0.65
        _wheelScroll(x, y, -6)
        time.sleep(0.2)

    def scrollUp(self):
        x = self.window.left + self.window.width * 0.58
        y = self.window.top + self.window.height * 0.65
        _wheelScroll(x, y, 6)
        time.sleep(0.2)

class AppConfig():
    def __init__(self):
        # here is where you can config setting
        #general setting
        self.RECOGNIZE_TITLES = {'Epic Seven',
                                 'BlueStacks App Player',
                                 'LDPlayer',
                                 'MuMu Player 12',
                                 '에픽세븐',
                                 'Google Play Games on PC Emulator'}        #if detected title show up in the select bar so that you don't need to manual enter
        #list of all the purchasable item
        self.ALL_ITEMS = [['cov.png', 'Covenant bookmark', 184000],
                          ['mys.png', 'Mystic medal', 280000],
                          ['fb.png', 'Friendship bookmark', 18000]]
        self.MANDATORY_PATH = {'cov.png', 'mys.png'}        #make item unable to be unselected
        self.DEBUG = False
        


if __name__ == '__main__':
    if not os.path.isdir('assets'):
        print('\'assets\' folder is missing! Make sure you have the assets folder in the same directory')
        raise SystemExit(1)

    config = AppConfig()

    print('Active windows:\n')
    for title in gw.getAllTitles():
        if title != '':
            print(title)
    print()

    win = input('Window title: ')
    if win not in gw.getAllTitles() or win == '':
        raise SystemExit('Wrong title, closing.')

    try:
        budget = int(input('Amount of skystone to spend: '))
    except ValueError:
        print('Invalid input, defaulting to 1000 skystone budget')
        budget = 1000

    include_friendship = input('Include friendship bookmark too? [y/N]: ').strip().lower() == 'y'

    ssr = SecretShopRefresh(title_name=win, budget=budget, join_thread=True)
    for path, name, price in config.ALL_ITEMS:
        if path == 'fb.png' and not include_friendship:
            continue
        ssr.addShopItem(path, name, price)

    input('Press Enter to start ...')
    print('Press Ctrl+C to stop refreshing')
    ssr.start()
