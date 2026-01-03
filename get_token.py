import requests
import getpass
import os

def get_token():
    print("=== 获取 MCP_AUTH_TOKEN ===")
    base_url = "http://localhost:5000"
    
    username = input("请输入用户名: ").strip()
    password = getpass.getpass("请输入密码: ").strip()
    
    login_url = f"{base_url}/auth/login"
    
    try:
        response = requests.post(
            login_url, 
            json={"username": username, "password": password},
            headers={"Content-Type": "application/json", "Accept": "application/json"}
        )
        
        if response.status_code == 200:
            data = response.json()
            if data.get("success"):
                token = data.get("token")
                print("\n✅ 登录成功！")
                print(f"MCP_AUTH_TOKEN: {token}")
                
                # Ask to save to .env
                save = input("\n是否将此 Token 写入 .env 文件？(y/n): ").lower()
                if save == 'y':
                    env_path = '.env'
                    lines = []
                    if os.path.exists(env_path):
                        with open(env_path, 'r', encoding='utf-8') as f:
                            lines = f.readlines()
                    
                    # Remove existing MCP_AUTH_TOKEN
                    lines = [line for line in lines if not line.startswith('MCP_AUTH_TOKEN=')]
                    
                    # Append new token
                    if lines and not lines[-1].endswith('\n'):
                        lines[-1] += '\n'
                    lines.append(f"MCP_AUTH_TOKEN={token}\n")
                    
                    with open(env_path, 'w', encoding='utf-8') as f:
                        f.writelines(lines)
                    print("✅ 已更新 .env 文件")
            else:
                print(f"\n❌ 登录失败: {data.get('error')}")
        else:
            print(f"\n❌ 请求失败: {response.status_code} {response.text}")
            
    except requests.exceptions.ConnectionError:
        print(f"\n❌ 无法连接到服务器 ({base_url})。请确保 Flask 应用正在运行。")
    except Exception as e:
        print(f"\n❌ 发生错误: {e}")

if __name__ == "__main__":
    get_token()
